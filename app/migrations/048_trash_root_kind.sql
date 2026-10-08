-- 048: 0.44.0 – Erweiterung von files.current_root_kind um 'trash'.
-- Die konservative Tabellen-Rebuild-Migration wird in app.database
-- durch _apply_trash_root_kind_migration innerhalb einer Transaktion ausgeführt.
-- Ein SQL ALTER COLUMN ist in SQLite nicht verfügbar.
SELECT 1;
