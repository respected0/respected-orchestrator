//! Read-only project file view. The renderer has no filesystem access at all; it may only ask this module about paths inside a folder the person
//! picked in the native folder dialog (this run, or an earlier one: the picked folders are remembered in a small file in the app's data folder). Paths are canonicalised first, so `..`, symlinks and junctions cannot leave the picked folder.
use serde::Serialize;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

pub const MAX_ENTRIES: usize = 500;
pub const MAX_FILE_BYTES: u64 = 256 * 1024;

#[derive(Default)]
pub struct Roots(pub Mutex<Vec<PathBuf>>, pub Option<PathBuf>);

#[derive(Serialize, Debug, PartialEq)]
pub struct Entry { pub name: String, pub dir: bool }

impl Roots {
    /// Roots that survive a restart: the folders the person picked earlier are read back from `file`, and every new pick is written to it.
    /// A missing or unreadable file only means nothing is remembered; it never grants anything the person did not pick.
    pub fn persistent(file: PathBuf) -> Self {
        let saved: Vec<String> = std::fs::read_to_string(&file).ok().and_then(|t| serde_json::from_str(&t).ok()).unwrap_or_default();
        let roots = saved.iter().filter_map(|p| Path::new(p).canonicalize().ok()).collect();
        Roots(Mutex::new(roots), Some(file))
    }
    /// Called only from the native folder picker.
    pub fn allow(&self, folder: &Path) {
        if let Ok(c) = folder.canonicalize() {
            let mut roots = self.0.lock().unwrap();
            if !roots.contains(&c) {
                roots.push(c);
                if let Some(f) = &self.1 {
                    let list: Vec<String> = roots.iter().map(|r| r.to_string_lossy().into_owned()).collect();
                    if let Some(dir) = f.parent() { let _ = std::fs::create_dir_all(dir); }
                    let _ = serde_json::to_string(&list).map(|j| std::fs::write(f, j));
                }
            }
        }
    }
    fn inside(&self, path: &Path) -> Result<PathBuf, String> {
        let c = path.canonicalize().map_err(|_| "Yol bulunamadı.".to_string())?;
        if self.0.lock().unwrap().iter().any(|r| c.starts_with(r)) { Ok(c) } else { Err("Bu klasörü daha önce seçmedin; klasörü yeniden seç.".into()) }
    }
    pub fn list(&self, path: &Path) -> Result<Vec<Entry>, String> {
        let dir = self.inside(path)?;
        let mut out: Vec<Entry> = std::fs::read_dir(&dir).map_err(|e| format!("Klasör okunamadı: {e}"))?
            .filter_map(|e| e.ok()).take(MAX_ENTRIES)
            .map(|e| Entry { name: e.file_name().to_string_lossy().into_owned(), dir: e.file_type().map(|t| t.is_dir()).unwrap_or(false) }).collect();
        out.sort_by(|a, b| b.dir.cmp(&a.dir).then(a.name.to_lowercase().cmp(&b.name.to_lowercase())));
        Ok(out)
    }
    pub fn read_text(&self, path: &Path) -> Result<String, String> {
        let file = self.inside(path)?;
        let meta = std::fs::metadata(&file).map_err(|e| format!("Dosya okunamadı: {e}"))?;
        if !meta.is_file() { return Err("Bu bir dosya değil.".into()); }
        if meta.len() > MAX_FILE_BYTES { return Err(format!("Dosya çok büyük (en çok {} KB gösterilir).", MAX_FILE_BYTES / 1024)); }
        let bytes = std::fs::read(&file).map_err(|e| format!("Dosya okunamadı: {e}"))?;
        if bytes.iter().take(8000).any(|b| *b == 0) { return Err("İkili dosya gösterilmez.".into()); }
        Ok(String::from_utf8_lossy(&bytes).into_owned())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tree() -> (PathBuf, PathBuf, Roots) {
        let base = std::env::temp_dir().join(format!("orch-files-{}-{}", std::process::id(), std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
        let proj = base.join("proj");
        std::fs::create_dir_all(proj.join("src")).unwrap();
        std::fs::write(proj.join("a.txt"), "selam").unwrap();
        std::fs::write(base.join("secret.txt"), "gizli").unwrap();
        let roots = Roots::default();
        roots.allow(&proj);
        (base, proj, roots)
    }

    #[test]
    fn lists_inside_the_picked_folder_directories_first() {
        let (_b, proj, roots) = tree();
        assert_eq!(roots.list(&proj).unwrap(), vec![Entry { name: "src".into(), dir: true }, Entry { name: "a.txt".into(), dir: false }]);
        assert_eq!(roots.read_text(&proj.join("a.txt")).unwrap(), "selam");
    }

    #[test]
    fn nothing_outside_the_picked_folder_is_readable_not_even_through_dotdot() {
        let (base, proj, roots) = tree();
        assert!(roots.list(&base).is_err());
        assert!(roots.read_text(&base.join("secret.txt")).is_err());
        assert!(roots.read_text(&proj.join("..").join("secret.txt")).is_err());
        assert!(Roots::default().list(&proj).is_err()); // no folder picked yet: nothing is allowed
    }

    #[test]
    fn picked_folders_are_remembered_across_restarts_and_only_those() {
        let (base, proj, _r) = tree();
        let store = base.join("data").join("picked.json");
        Roots::persistent(store.clone()).allow(&proj);
        let again = Roots::persistent(store);
        assert!(again.list(&proj).is_ok());
        assert!(again.list(&base).is_err());
        assert!(Roots::persistent(base.join("none.json")).list(&proj).is_err());
    }

    #[test]
    fn big_binary_and_non_files_are_refused() {
        let (_b, proj, roots) = tree();
        std::fs::write(proj.join("big.txt"), vec![b'a'; (MAX_FILE_BYTES + 1) as usize]).unwrap();
        std::fs::write(proj.join("bin.dat"), [1u8, 0, 2]).unwrap();
        assert!(roots.read_text(&proj.join("big.txt")).unwrap_err().contains("büyük"));
        assert!(roots.read_text(&proj.join("bin.dat")).unwrap_err().contains("İkili"));
        assert!(roots.read_text(&proj.join("src")).is_err());
        assert!(roots.read_text(&proj.join("yok.txt")).is_err());
    }
}
