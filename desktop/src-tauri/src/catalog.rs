// Generated from src/respected_orchestrator/engine/catalog.py by `python -m respected_orchestrator.engine.catalog`. Do not edit.
pub const SESSION_COMMANDS: [&str; 19] = ["agent.describe", "sessions.list", "session.start", "session.events", "session.send", "session.retry", "session.interrupt", "session.cancel", "session.resume", "session.models", "session.defaults", "session.defaults.set", "session.mode.set", "session.transcript", "session.forget", "session.rename", "session.pin", "session.archive", "session.export"];
pub const TASK_COMMANDS: [&str; 4] = ["task.start", "task.status", "task.cancel", "task.retry"];
pub const TERMINAL_COMMANDS: [&str; 5] = ["terminal.list", "terminal.start", "terminal.input", "terminal.resize", "terminal.kill"];
pub const VOICE_COMMANDS: [&str; 4] = ["voice.start", "voice.feed", "voice.stop", "voice.cancel"];
pub const ATTACH_COMMANDS: [&str; 5] = ["attachment.arm", "attachment.part", "attachment.stage", "attachment.cancel", "attachment.delete"];
pub const READ_COMMANDS: [&str; 15] = ["catalog.list", "settings.schema", "settings.readback", "settings.validate", "runs.list", "projects.list", "project.status", "activity.list", "capabilities.recommend", "team.view", "analytics.summary", "voice.status", "attachment.status", "attachment.preview", "attachment.list"];
