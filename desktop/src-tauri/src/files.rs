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

#[derive(Serialize, Debug, PartialEq)]
pub struct Instruction { pub path: String, pub name: String, pub folder: String, pub scope: String, pub exists: bool }

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
    pub fn read_text(&self, path: &Path) -> Result<String, String> { read_regular(&self.inside(path)?) }

    /// Every instruction file the agents may read for this project: the two at the root (also when missing, so they can be created),
    /// the ones in subfolders up to a bounded depth, and the two fixed user-level files. Only those two names leave a picked folder.
    pub fn instructions(&self, folder: &Path) -> Result<Vec<Instruction>, String> { self.instructions_at(folder, user_home().as_deref()) }

    fn instructions_at(&self, folder: &Path, home: Option<&Path>) -> Result<Vec<Instruction>, String> {
        let root = self.inside(folder)?;
        if !root.is_dir() { return Err("Bu bir klasör değil.".into()); }
        let mut out: Vec<Instruction> = INSTRUCTION_FILES.iter().map(|name| instruction(&root.join(name), name, "root")).collect();
        let mut stack = vec![(root, 0usize)];
        let mut seen = 0usize;
        while let Some((dir, depth)) = stack.pop() {
            if seen >= MAX_SCAN_DIRS || out.len() >= MAX_INSTRUCTION_FILES { break; }
            seen += 1;
            let Ok(entries) = std::fs::read_dir(&dir) else { continue };
            let mut names: Vec<_> = entries.filter_map(|e| e.ok()).collect();
            names.sort_by(|a, b| a.file_name().to_string_lossy().to_lowercase().cmp(&b.file_name().to_string_lossy().to_lowercase()));
            let mut below = Vec::new();
            for e in names {
                let name = e.file_name().to_string_lossy().into_owned();
                let Ok(kind) = e.file_type() else { continue };
                if kind.is_dir() {
                    if depth < MAX_INSTRUCTION_DEPTH && !name.starts_with('.') && !SKIP_DIRS.contains(&name.as_str()) { below.push(e.path()); }
                } else if kind.is_file() && depth > 0 && INSTRUCTION_FILES.contains(&name.as_str()) {
                    out.push(instruction(&e.path(), &name, "subfolder"));
                }
            }
            for path in below.into_iter().rev() { stack.push((path, depth + 1)); }
        }
        if let Some(home) = home {
            for (name, dir) in USER_INSTRUCTION_FILES {
                let path = home.join(dir).join(name);
                if std::fs::symlink_metadata(&path).map(|m| m.is_file()).unwrap_or(false) { out.push(instruction(&path, name, "user")); }
            }
        }
        Ok(out)
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
/// User-level files are read by name only, from these two fixed folders under the user's home.
pub const USER_INSTRUCTION_FILES: [(&str, &str); 2] = [("CLAUDE.md", ".claude"), ("AGENTS.md", ".codex")];
pub const MAX_SCAN_DIRS: usize = 120;
pub const MAX_INSTRUCTION_DEPTH: usize = 3;
pub const MAX_INSTRUCTION_FILES: usize = 40;
const SKIP_DIRS: [&str; 6] = ["node_modules", "target", "dist", "build", "vendor", "__pycache__"];

fn user_home() -> Option<PathBuf> {
    std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME")).map(PathBuf::from).filter(|p| !p.as_os_str().is_empty())
}

fn instruction(path: &Path, name: &str, scope: &str) -> Instruction {
    Instruction { path: path.to_string_lossy().into_owned(), name: name.into(), folder: path.parent().map(|p| p.to_string_lossy().into_owned()).unwrap_or_default(), scope: scope.into(), exists: path.is_file() }
}

fn read_regular(file: &Path) -> Result<String, String> {
    let meta = std::fs::metadata(file).map_err(|e| format!("Dosya okunamadı: {e}"))?;
    if !meta.is_file() { return Err("Bu bir dosya değil.".into()); }
    if meta.len() > MAX_FILE_BYTES { return Err(format!("Dosya çok büyük (en çok {} KB gösterilir).", MAX_FILE_BYTES / 1024)); }
    let bytes = std::fs::read(file).map_err(|e| format!("Dosya okunamadı: {e}"))?;
    if bytes.iter().take(8000).any(|b| *b == 0) { return Err("İkili dosya gösterilmez.".into()); }
    Ok(String::from_utf8_lossy(&bytes).into_owned())
}

/// Reads one of the two fixed user-level instruction files; no other name or path is accepted.
pub fn read_user_instruction(name: &str) -> Result<String, String> {
    let home = user_home().ok_or("Kullanıcı klasörü bulunamadı.")?;
    let dir = USER_INSTRUCTION_FILES.iter().find(|(n, _)| *n == name).map(|(_, d)| *d).ok_or("Yalnız kullanıcı düzeyindeki CLAUDE.md ve AGENTS.md okunur.")?;
    let path = home.join(dir).join(name);
    if !std::fs::symlink_metadata(&path).map(|m| m.is_file()).unwrap_or(false) { return Err("Kullanıcı talimat dosyası yok.".into()); }
    read_regular(&path)
}

/// The renderer asks to save an instruction file; the person confirms it in a native dialog that names the real path, then the file is
/// replaced in one step. `Ok(false)`: the person said no and nothing was written.
pub fn request_write(roots: &Roots, folder: &Path, name: &str, text: &str, expected: Option<&str>, force: bool, presence: &dyn crate::approval::Presence, gate: &crate::approval::Gate) -> Result<bool, String> {
    if text.len() as u64 > MAX_FILE_BYTES { return Err(format!("Dosya çok büyük (en çok {} KB).", MAX_FILE_BYTES / 1024)); }
    if text.contains('\0') { return Err("Metin geçersiz karakter içeriyor.".into()); }
    let target = roots.instruction_path(folder, name)?;
    let exists = target.is_file();
    let current = if exists && std::fs::metadata(&target).map(|m| m.len() <= MAX_FILE_BYTES).unwrap_or(false) {
        std::fs::read(&target).ok().map(|b| String::from_utf8_lossy(&b).into_owned())
    } else { None };
    let changed = exists != expected.is_some() || expected.map(|e| current.as_deref() != Some(e)).unwrap_or(false);
    if changed && !force { return Err("FILE_CHANGED: Dosya bu arada dışarıda değişmiş. Yeniden okuyup karşılaştır ya da bilerek üzerine yaz.".into()); }
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
        assert_eq!(request_write(&roots, &proj, "AGENTS.md", "kurallar\n", None, false, &no, &gate), Ok(false));
        assert!(!proj.join("AGENTS.md").exists() && no.1.borrow()[0].contains("Yeni dosya"));
        assert_eq!(request_write(&roots, &proj, "AGENTS.md", "kurallar\n", None, false, &yes, &gate), Ok(true));
        assert_eq!(std::fs::read_to_string(proj.join("AGENTS.md")).unwrap(), "kurallar\n");
        assert_eq!(request_write(&roots, &proj.join("src"), "CLAUDE.md", "alt\n", None, false, &yes, &gate), Ok(true)); // a folder inside a picked one
        assert_eq!(request_write(&roots, &proj, "AGENTS.md", "yeni\n", Some("kurallar\n"), false, &yes, &gate), Ok(true));
        assert!(yes.1.borrow().last().unwrap().contains("üzerine yazılır") && std::fs::read_to_string(proj.join("AGENTS.md")).unwrap() == "yeni\n");
        let asked = yes.1.borrow().len();
        for (folder, name) in [(proj.clone(), "a.txt"), (proj.clone(), "..\\secret.txt"), (proj.clone(), "agents.md"), (proj.clone(), "src\\AGENTS.md"), (base.clone(), "AGENTS.md"), (proj.join("a.txt"), "AGENTS.md")] {
            assert!(request_write(&roots, &folder, name, "x", None, false, &yes, &gate).is_err(), "{folder:?} {name}");
        }
        assert!(request_write(&roots, &proj, "AGENTS.md", &"x".repeat(MAX_FILE_BYTES as usize + 1), None, false, &yes, &gate).is_err());
        assert!(request_write(&roots, &proj, "AGENTS.md", "a\0b", None, false, &yes, &gate).is_err());
        std::fs::create_dir(proj.join("CLAUDE.md")).unwrap();
        assert!(request_write(&roots, &proj, "CLAUDE.md", "x", None, false, &yes, &gate).is_err(), "a folder with that name is not overwritten");
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
    fn a_write_is_refused_when_the_file_changed_outside_and_force_still_works() {
        let (base, proj, roots) = tree();
        let gate = crate::approval::Gate::default();
        let yes = Say(true, Default::default());
        assert_eq!(request_write(&roots, &proj, "AGENTS.md", "bir\n", None, false, &yes, &gate), Ok(true));
        std::fs::write(proj.join("AGENTS.md"), "başka biri yazdı\n").unwrap();
        let err = request_write(&roots, &proj, "AGENTS.md", "benim\n", Some("bir\n"), false, &yes, &gate).unwrap_err();
        assert!(err.starts_with("FILE_CHANGED:") && err.contains("dışarıda"), "{err}");
        assert_eq!(std::fs::read_to_string(proj.join("AGENTS.md")).unwrap(), "başka biri yazdı\n");
        assert_eq!(request_write(&roots, &proj, "AGENTS.md", "benim\n", Some("bir\n"), true, &yes, &gate), Ok(true));
        assert_eq!(std::fs::read_to_string(proj.join("AGENTS.md")).unwrap(), "benim\n");
        std::fs::remove_file(proj.join("AGENTS.md")).unwrap();
        assert!(request_write(&roots, &proj, "AGENTS.md", "x", Some("benim\n"), true, &yes, &gate).is_ok());
        assert!(request_write(&roots, &proj, "AGENTS.md", "x", None, false, &yes, &gate).unwrap_err().starts_with("FILE_CHANGED:"));
        std::fs::remove_dir_all(base).ok();
    }

    #[test]
    fn instruction_files_are_found_at_the_root_in_subfolders_and_at_the_user_level() {
        let (base, proj, roots) = tree();
        std::fs::write(proj.join("AGENTS.md"), "kök").unwrap();
        std::fs::write(proj.join("src").join("CLAUDE.md"), "alt").unwrap();
        std::fs::create_dir_all(proj.join("a").join("b").join("c")).unwrap();
        std::fs::write(proj.join("a").join("b").join("c").join("AGENTS.md"), "derin").unwrap();
        std::fs::create_dir_all(proj.join("a").join("b").join("c").join("d")).unwrap();
        std::fs::write(proj.join("a").join("b").join("c").join("d").join("AGENTS.md"), "çok derin").unwrap();
        std::fs::create_dir_all(proj.join(".git")).unwrap();
        std::fs::write(proj.join(".git").join("AGENTS.md"), "gizli").unwrap();
        std::fs::create_dir_all(proj.join("node_modules")).unwrap();
        std::fs::write(proj.join("node_modules").join("AGENTS.md"), "paket").unwrap();
        let home = base.join("home");
        std::fs::create_dir_all(home.join(".claude")).unwrap();
        std::fs::write(home.join(".claude").join("CLAUDE.md"), "kullanıcı").unwrap();
        let listed = roots.instructions_at(&proj, Some(&home)).unwrap();
        let names: Vec<(&str, &str, bool)> = listed.iter().map(|i| (i.name.as_str(), i.scope.as_str(), i.exists)).collect();
        assert_eq!(names, vec![
            ("AGENTS.md", "root", true), ("CLAUDE.md", "root", false),
            ("AGENTS.md", "subfolder", true), ("CLAUDE.md", "subfolder", true),
            ("CLAUDE.md", "user", true),
        ]);
        assert!(listed.iter().all(|i| !i.path.contains("node_modules") && !i.path.contains(".git") && !i.path.ends_with(r"\d\AGENTS.md")));
        assert!(roots.instructions_at(&base, Some(&home)).is_err(), "outside a picked folder");
        std::fs::remove_dir_all(base).ok();
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
