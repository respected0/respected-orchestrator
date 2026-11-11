//! Project file view: read-only, with one exception at the end of this file (the two instruction files, after a native confirmation). The renderer has no filesystem access at all; it may only ask this module about paths inside a folder the person
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

    /// Where an instruction file of a picked folder lives. The folder must be one the person picked (or lie inside one) and the name one of
    /// the two agents read; a file that is already there must really be a plain file in that folder, not a link that leads somewhere else.
    pub fn instruction_path(&self, folder: &Path, name: &str) -> Result<PathBuf, String> {
        if !INSTRUCTION_FILES.contains(&name) { return Err("Yalnız AGENTS.md ve CLAUDE.md yazılabilir.".into()); }
        let dir = self.inside(folder)?;
        if !dir.is_dir() { return Err("Bu bir klasör değil.".into()); }
        let target = dir.join(name);
        if target.symlink_metadata().is_ok() {
            let real = target.canonicalize().map_err(|_| "Dosya okunamadı.".to_string())?;
            if !real.is_file() || real.to_string_lossy().to_lowercase() != target.to_string_lossy().to_lowercase() { return Err("Bu ad bir dosyayı göstermiyor.".into()); }
        }
        Ok(target)
    }
}

/// The only files this program writes into a project: the instruction files agents read (KALAN_ISLER 4.7).
pub const INSTRUCTION_FILES: [&str; 2] = ["AGENTS.md", "CLAUDE.md"];

/// The renderer asks to save an instruction file; the person confirms it in a native dialog that names the real path, then the file is
/// replaced in one step. `Ok(false)`: the person said no and nothing was written.
pub fn request_write(roots: &Roots, folder: &Path, name: &str, text: &str, presence: &dyn crate::approval::Presence, gate: &crate::approval::Gate) -> Result<bool, String> {
    if text.len() as u64 > MAX_FILE_BYTES { return Err(format!("Dosya çok büyük (en çok {} KB).", MAX_FILE_BYTES / 1024)); }
    if text.contains('\0') { return Err("Metin geçersiz karakter içeriyor.".into()); }
    let target = roots.instruction_path(folder, name)?;
    let _guard = gate.enter().ok_or("Başka bir onay penceresi açık.")?;
    let shown: String = target.to_string_lossy().trim_start_matches(r"\\?\").chars().filter(|c| !c.is_control()).collect();
    let what = if target.exists() { "Var olan dosyanın üzerine yazılır." } else { "Yeni dosya oluşturulur." };
    if !presence.ask("Respected Orchestrator: talimat dosyası", &format!("Bu dosya kaydedilsin mi?\n\n{shown}\n{} satır, {} bayt. {what}\n\nAjanlar bu dosyayı talimat olarak okur. Varsayılan yanıt Hayır'dır.", text.lines().count(), text.len())) {
        return Ok(false);
    }
    let temp = target.with_file_name(format!("{name}.orch-tmp"));
    std::fs::write(&temp, text).map_err(|e| format!("Dosya yazılamadı: {e}"))?;
    std::fs::rename(&temp, &target).map_err(|e| { let _ = std::fs::remove_file(&temp); format!("Dosya yazılamadı: {e}") })?;
    Ok(true)
}

/// Exported history is not a project file: it goes wherever the person points the native save dialog, at most 4 MB, in one write.
/// The instruction-file path above (which is gated and limited to AGENTS.md/CLAUDE.md) is deliberately not used here.
pub const MAX_EXPORT_BYTES: usize = 4 * 1024 * 1024;

/// A plain file name for the save dialog: no path, no control characters, no Windows-reserved punctuation.
pub fn export_name(name: &str) -> Result<&str, String> {
    let n = name.trim();
    let bad = n.is_empty() || n.chars().count() > 120 || n == "." || n == ".."
        || n.chars().any(|c| c.is_control() || matches!(c, '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|'));
    if bad { Err("Dosya adı geçersiz.".into()) } else { Ok(n) }
}

pub fn save_text(path: &Path, text: &str) -> Result<(), String> {
    if !path.is_absolute() { return Err("Yol geçersiz.".into()); }
    let name = path.file_name().and_then(|n| n.to_str()).ok_or("Dosya adı geçersiz.")?;
    export_name(name)?;
    if text.len() > MAX_EXPORT_BYTES { return Err("Dosya çok büyük (en çok 4 MB).".into()); }
    if text.contains('\0') { return Err("Metin geçersiz karakter içeriyor.".into()); }
    std::fs::write(path, text.as_bytes()).map_err(|e| format!("Dosya yazılamadı: {e}"))
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

    struct Say(bool, std::cell::RefCell<Vec<String>>);
    impl crate::approval::Presence for Say {
        fn ask(&self, _t: &str, text: &str) -> bool { self.1.borrow_mut().push(text.to_string()); self.0 }
    }

    #[test]
    fn only_the_two_instruction_files_of_a_picked_folder_are_written_and_only_after_a_yes() {
        let (base, proj, roots) = tree();
        let gate = crate::approval::Gate::default();
        let (no, yes) = (Say(false, Default::default()), Say(true, Default::default()));
        assert_eq!(request_write(&roots, &proj, "AGENTS.md", "kurallar\n", &no, &gate), Ok(false));
        assert!(!proj.join("AGENTS.md").exists() && no.1.borrow()[0].contains("Yeni dosya"));
        assert_eq!(request_write(&roots, &proj, "AGENTS.md", "kurallar\n", &yes, &gate), Ok(true));
        assert_eq!(std::fs::read_to_string(proj.join("AGENTS.md")).unwrap(), "kurallar\n");
        assert_eq!(request_write(&roots, &proj.join("src"), "CLAUDE.md", "alt\n", &yes, &gate), Ok(true)); // a folder inside a picked one
        assert_eq!(request_write(&roots, &proj, "AGENTS.md", "yeni\n", &yes, &gate), Ok(true));
        assert!(yes.1.borrow().last().unwrap().contains("üzerine yazılır") && std::fs::read_to_string(proj.join("AGENTS.md")).unwrap() == "yeni\n");
        let asked = yes.1.borrow().len();
        for (folder, name) in [(proj.clone(), "a.txt"), (proj.clone(), "..\\secret.txt"), (proj.clone(), "agents.md"), (proj.clone(), "src\\AGENTS.md"), (base.clone(), "AGENTS.md"), (proj.join("a.txt"), "AGENTS.md")] {
            assert!(request_write(&roots, &folder, name, "x", &yes, &gate).is_err(), "{folder:?} {name}");
        }
        assert!(request_write(&roots, &proj, "AGENTS.md", &"x".repeat(MAX_FILE_BYTES as usize + 1), &yes, &gate).is_err());
        assert!(request_write(&roots, &proj, "AGENTS.md", "a\0b", &yes, &gate).is_err());
        std::fs::create_dir(proj.join("CLAUDE.md")).unwrap();
        assert!(request_write(&roots, &proj, "CLAUDE.md", "x", &yes, &gate).is_err(), "a folder with that name is not overwritten");
        assert_eq!(yes.1.borrow().len(), asked, "a refused request never reaches the dialog");
        assert_eq!(std::fs::read_to_string(base.join("secret.txt")).unwrap(), "gizli");
        std::fs::remove_dir_all(&base).ok();
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
    fn export_names_are_plain_files_and_sizes_are_bounded() {
        for good in ["sohbet.md", "sohbet.json", "başlık (1).md"] { assert_eq!(export_name(good), Ok(good)); }
        for bad in ["", "..", ".", "a/b.md", "a\\b.md", "a:b.md", "a?.md", "a\u{0000}.md", &"x".repeat(121)] { assert!(export_name(bad).is_err(), "{bad:?}"); }
        let (base, _proj, _roots) = tree();
        let file = base.join("sohbet.md");
        let text = "Türkçe metin ✓\n";
        assert_eq!(save_text(&file, text), Ok(()));
        assert_eq!(std::fs::read_to_string(&file).unwrap(), text);
        assert!(save_text(&base, "x").is_err(), "a directory is not a file");
        assert!(save_text(Path::new("sohbet.md"), "x").is_err(), "a relative path is refused");
        assert!(save_text(&base.join("a/b.md"), "x").is_err());
        assert!(save_text(&base.join("a\0b.md"), "x").is_err());
        assert!(save_text(&file, "a\0b").is_err());
        assert!(save_text(&file, &"a".repeat(MAX_EXPORT_BYTES + 1)).unwrap_err().contains("büyük"));
        std::fs::remove_dir_all(&base).ok();
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
