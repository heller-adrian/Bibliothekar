-- 038: Nicht blockierende Zusatzdateien in Archivänderungen explizit markieren.
--
-- Damit können benutzereigene Fremddateien und nachweislich byte-identische
-- XMP-/Export-Dubletten sichtbar bleiben, ohne den manuellen Archivabschluss
-- zu blockieren.
ALTER TABLE event_change_asset_reviews
    ADD COLUMN advisory INTEGER NOT NULL DEFAULT 0;

ALTER TABLE event_change_asset_reviews
    ADD COLUMN advisory_reason TEXT NOT NULL DEFAULT '';
