# RC3 acceptance candidate (not published)

This compose template preserves the RC2 mount, helper, UID/GID 568:568 and read-only archive contracts. The image tag is a placeholder until explicit publication approval; no registry push is performed by acceptance QA. Existing host paths are deliberately unchanged. Do not create or adjust production datasets/ACLs through this QA.

The SD mount area still requires the previously documented NFSv4 ACL separation: the web UID/GID 568:568 needs read/traverse, not write, on the protected helper mount namespace and parents. The helper must establish and prove its own mount ownership and effective read-only status. Do not bypass its checks or grant broad write access. Automatic catalogue provisioning remains a separate deployment task.

After technical acceptance, repeat the R01–R06 smartphone/TrueNAS checks from the RC3 targeted QA: ordinary repeat backup without an empty job, explicit integrity/missing-copy recovery with synthetic media, new JPG/RAW/video and duplicate counts, EN/DE messages, long planned/actual preview on Safari/Android, orientation/close/reopen, and current versus historical archive counts. The RC2 mobile trash regression is still open; B12 remains deferred. Accepted F13/F24 residual risks are unchanged.
