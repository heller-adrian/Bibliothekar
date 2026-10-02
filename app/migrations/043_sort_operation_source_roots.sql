-- 043: Physische Quellwurzel pro Sortieroperation einfrieren.
--
-- Ein Sortierlauf kann nach der Multi-Library-/Central-Stock-Migration Dateien
-- aus unterschiedlichen physischen Wurzeln enthalten. Die historische
-- source_root_kind-Klassifikation reicht dafür nicht aus. Für sicheren
-- Neustart/Rollback wird deshalb der tatsächlich geprüfte Root jeder
-- Kamera-/Asset-Operation dauerhaft gespeichert.
ALTER TABLE sort_operations
ADD COLUMN source_root_path TEXT NOT NULL DEFAULT '';

ALTER TABLE sort_asset_operations
ADD COLUMN source_root_path TEXT NOT NULL DEFAULT '';
