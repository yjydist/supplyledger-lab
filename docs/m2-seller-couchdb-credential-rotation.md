# M2 Seller CouchDB credential rotation

This runbook addresses one Seller CouchDB admin password disclosed by an unsanitized local Docker-inspect tool response. The value did not enter Git or the redacted evidence. Execute this as a separate reviewed gate **before** integrating the #16 Discovery configuration change. The live Seller Peer and rendered core.yaml must still use the current pre-Discovery configuration. After a successful rotation, capture a fresh M1, six-env, nine-container and volume baseline; #16 must begin its own staging from that baseline. Seller Peer is deliberately recreated once here and once for #16.

Trace: SPEC.md §§3.2, 5.4, 16.4, 19.1; #16 node readiness and #18 NET-07. Test ID M2-SELLER-CDB-ROT-01. This is a **local Seller cold-state recovery point** for a credential change, not the full-network cold backup or restore drill required by §16.4 and not T-OPS-08.

## Why recreation is required

Compose injects COUCHDB_USER/COUCHDB_PASSWORD from .secrets/couchdb/seller.env into couchdb0-seller and CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME/PASSWORD from .secrets/peer-couchdb/seller.env into peer0-seller. The two files are ignored, mode 0600, and their parent directories are mode 0700. The CouchDB service mounts only its named data volume at /opt/couchdb/data; it does not mount /opt/couchdb/etc. The pinned [CouchDB 3.4.2 entrypoint](https://github.com/apache/couchdb-docker/blob/main/3.4.2/docker-entrypoint.sh#L479-L550) writes the admin into /opt/couchdb/etc/local.d/docker.ini only if absent. Changing an env file or restarting an existing container does not replace its effective admin. A force-recreated CouchDB container starts with a fresh non-persistent config filesystem and reuses the same named data volume. Probe the effective admin after recreation; do not infer success from env-file equality.

Never print env-file contents, a full Compose config, docker inspect Config.Env, CouchDB admin config, an Authorization header, a session cookie, or a raw password. The Docker host administrator can inspect container env and the host-controlled secret files; rotation does not remove that trust boundary. The only tracked evidence may contain key names, file fingerprints, status codes, container/volume identities and sanitized failure phases.

## Before the first live command

Require reviewed RUNBOOK GO, a clean main containing this runbook but **not** the #16 Discovery template patch, the original #17 block, and a quiet channel window with no #19 configuration update or business writer. Stop if the running Seller Peer or CouchDB is already unhealthy, if its credential env does not equal the two ignored source files, or if the three rendered Peer YAMLs already differ from the current tracked templates. Keep the #18 first Discovery FAIL files untouched.

Create one new Git-ignored mode-0700 evidence directory. Each later command block is the body of **one** mode-0600 .command.sh and begins by sourcing scripts/m2-seller-couchdb-rotation-state.sh, which reloads/validates the private run path and sets fail-closed Bash/umask 077. Run each file separately and retain its own mode-0600 .log and .exit, plus UTC start/end. Stop on any nonzero exit or unexpected HTTP/Peer response; never use reset, down -v, a volume prune, or a generic network startup. Do not place a password literal in a command file.

~~~sh
set -euo pipefail
umask 077
ROTATION_DIR=".runtime/m2-seller-couchdb-rotation-$(date -u +%Y%m%dT%H%M%SZ)"
test ! -e "$ROTATION_DIR"
test ! -e .runtime/m2-seller-couchdb-rotation-active
mkdir -m 700 "$ROTATION_DIR"
mkdir -m 700 "$ROTATION_DIR/backup" "$ROTATION_DIR/old-secrets"
mkdir -m 700 "$ROTATION_DIR/old-secrets/couchdb" "$ROTATION_DIR/old-secrets/peer-couchdb"
printf '%s\n' "$ROTATION_DIR" > .runtime/m2-seller-couchdb-rotation-active
git check-ignore --quiet "$ROTATION_DIR"
~~~

For an individual recorded step, save exactly one native operation after the source line in its .command.sh. The capture shell itself must have umask 077. The following envelope demonstrates the required independent exit gate; substitute each reviewed step name, require a new path and inspect its actual log/status before the next step. A tar-export command redirects its binary stdout to its private archive inside the .command.sh, while the surrounding capture collects only stderr.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
STEP=preflight-doctor
test ! -e "$ROTATION_DIR/$STEP.command.sh"
test ! -e "$ROTATION_DIR/$STEP.log"
test ! -e "$ROTATION_DIR/$STEP.exit"
cat > "$ROTATION_DIR/$STEP.command.sh" <<'SH'
#!/usr/bin/env bash
source scripts/m2-seller-couchdb-rotation-state.sh
make doctor
SH
chmod 600 "$ROTATION_DIR/$STEP.command.sh"
set +e
bash "$ROTATION_DIR/$STEP.command.sh" > "$ROTATION_DIR/$STEP.log" 2>&1
STEP_RC=$?
set -e
printf '%s\n' "$STEP_RC" > "$ROTATION_DIR/$STEP.exit"
test "$STEP_RC" -eq 0
~~~

Before stopping anything, record separate command/log/exit triads for git status, make doctor, make network-config, make verify-m1, make verify-m2-nodes, original-block SHA and the two native Seller channel list/getinfo calls. The original block artifact must equal SHA-256 b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a. Record source commit, versions.lock.yaml SHA-256, image digests, old rendered Peer YAML hashes, all nine node IDs/states, nine named-volume Name/CreatedAt pairs, and the Seller native height/header hash. Use the exact own-org, nonroot, read-only tools command in [m2-peer-client-mtls.md](m2-peer-client-mtls.md) twice, once ending channel list and once ending channel getinfo -c supplychannel. Its signed CSCC query does not submit a channel transaction. Record any txId or validation code only if an actual result provides one; these queries ordinarily do not.

In particular, write each Seller volume's exact Name/CreatedAt before stopping anything; the later tar command must compare against these records **before mounting** so Docker cannot silently create an empty volume:

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test ! -e "$ROTATION_DIR/backup/couchdb-volume.before"
docker volume inspect --format '{{.Name}} {{.CreatedAt}}' supplyledger_couchdb0_seller_data > "$ROTATION_DIR/backup/couchdb-volume.before"
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test ! -e "$ROTATION_DIR/backup/peer-volume.before"
docker volume inspect --format '{{.Name}} {{.CreatedAt}}' supplyledger_peer0_seller_ledger > "$ROTATION_DIR/backup/peer-volume.before"
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test ! -e "$ROTATION_DIR/backup/env.before.sha256"
shasum -a 256 .secrets/couchdb/seller.env .secrets/peer-couchdb/seller.env \
  > "$ROTATION_DIR/backup/env.before.sha256"
~~~

Use the fixed read-only runtime checker below as its own command/log/exit. It captures docker inspect JSON inside Python, compares only the required values in memory, and emits no raw Config.Env, password, response body or header. It requires the exact Seller mount destinations, types, source ownership and read-only bits, allowing only the two expected anonymous Peer image volumes; Docker Desktop's /host_mnt prefix is normalized before source comparison. An extra cross-org private mount, Docker socket or CouchDB config bind is rejected. It also checks exact networks and no published ports. Record other seven IDs separately with docker inspect --format '{{.Id}}', never a full inspect object. The current repository preparation code generates existing passwords with secrets.token_urlsafe(32); it validates both env files and rejects mismatches.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
python3 scripts/verify-m2-seller-couchdb-runtime.py --component both
~~~

## Quiesce and make the local cold-state recovery point

Freeze writers and confirm no in-flight channel operation. Stop Seller Peer, then Seller CouchDB, with two separate native Compose commands. Confirm both are stopped before reading their volumes. Buyer/Carrier and Orderers remain running but must be kept free of new writes during this local snapshot. This is not a full-network disaster-recovery snapshot.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca stop peer0-seller
~~~

Require Seller Peer status exited and record that check before the next native step.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca stop couchdb0-seller
~~~

Require CouchDB status exited. Copy rollback inputs in a separate private file-copy step, checking absent destinations first:

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
test ! -e "$ROTATION_DIR/old-secrets/couchdb/seller.env"
test ! -e "$ROTATION_DIR/old-secrets/peer-couchdb/seller.env"
test ! -e "$ROTATION_DIR/backup/peer0-seller.yaml"
install -m 600 .secrets/couchdb/seller.env "$ROTATION_DIR/old-secrets/couchdb/seller.env"
install -m 600 .secrets/peer-couchdb/seller.env "$ROTATION_DIR/old-secrets/peer-couchdb/seller.env"
install -m 600 .runtime/network-config/peer0-seller.yaml "$ROTATION_DIR/backup/peer0-seller.yaml"
~~~

Use the locked local supply-tools image with no network and read-only volume mounts to stream each stopped named volume into a host-owned mode-0600 archive. The only stdout is the redirected binary tar stream; never display it. Keep command, stderr and exit records separately. If an archive command fails, the partial archive is unusable and rotation stops.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
test "$(docker volume inspect --format '{{.Name}} {{.CreatedAt}}' supplyledger_couchdb0_seller_data)" = "$(cat "$ROTATION_DIR/backup/couchdb-volume.before")"
test ! -e "$ROTATION_DIR/backup/couchdb-data.tar"
docker run --rm --pull=never --platform linux/arm64 --network none --read-only \
  --user 0:0 --mount type=volume,src=supplyledger_couchdb0_seller_data,dst=/source,readonly \
  --entrypoint tar supply-tools:m0-fabric3.1.5-ca1.5.22 \
  -C /source -cf - . > "$ROTATION_DIR/backup/couchdb-data.tar"
~~~

Require this command's own exit 0, a nonempty mode-0600 archive, and unchanged CouchDB volume identity before exporting the Peer volume.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
test "$(docker volume inspect --format '{{.Name}} {{.CreatedAt}}' supplyledger_peer0_seller_ledger)" = "$(cat "$ROTATION_DIR/backup/peer-volume.before")"
test ! -e "$ROTATION_DIR/backup/peer-ledger.tar"
docker run --rm --pull=never --platform linux/arm64 --network none --read-only \
  --user 0:0 --mount type=volume,src=supplyledger_peer0_seller_ledger,dst=/source,readonly \
  --entrypoint tar supply-tools:m0-fabric3.1.5-ca1.5.22 \
  -C /source -cf - . > "$ROTATION_DIR/backup/peer-ledger.tar"
~~~

Require its separate exit 0 and nonempty mode-0600 archive. Run the following offline archive validation only after both exports pass. It writes any checksum and extraction output inside the ignored private directory and never to tracked evidence.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
tar -tf "$ROTATION_DIR/backup/couchdb-data.tar" > /dev/null
tar -tf "$ROTATION_DIR/backup/peer-ledger.tar" > /dev/null
shasum -a 256 "$ROTATION_DIR/backup/couchdb-data.tar" "$ROTATION_DIR/backup/peer-ledger.tar" \
  "$ROTATION_DIR/old-secrets/couchdb/seller.env" \
  "$ROTATION_DIR/old-secrets/peer-couchdb/seller.env" > "$ROTATION_DIR/backup/checksums.sha256"
python3 - <<'PY'
import os
import tarfile
from pathlib import Path, PurePosixPath

root = Path(os.environ["ROTATION_DIR"]) / "backup"
for name in ("couchdb-data.tar", "peer-ledger.tar"):
    with tarfile.open(root / name, "r:") as archive:
        members = archive.getmembers()
        assert members, "empty archive"
        for member in members:
            path = PurePosixPath(member.name)
            assert not path.is_absolute() and ".." not in path.parts
            assert member.isfile() or member.isdir(), "unsafe archive member"
print("PASS: two nonempty archives contain only relative files and directories")
PY
mkdir -m 700 "$ROTATION_DIR/backup/extract-couchdb" "$ROTATION_DIR/backup/extract-peer"
tar -xf "$ROTATION_DIR/backup/couchdb-data.tar" -C "$ROTATION_DIR/backup/extract-couchdb"
tar -xf "$ROTATION_DIR/backup/peer-ledger.tar" -C "$ROTATION_DIR/backup/extract-peer"
shasum -a 256 -c "$ROTATION_DIR/backup/checksums.sha256" > "$ROTATION_DIR/backup/checksums-verify.log"
~~~

Require both native tar exits 0, nonempty archives, mode 0600 archive/manifest files, mode 0700 directories, successful tar listing, the path/type guard, successful extraction into private scratch directories, recorded hashes and unchanged named-volume identity. Retain association with the original block/header, Seller height, old core.yaml hash, Seller MSP/TLS fingerprints and locked versions. This tests archive readability, not a Fabric/CouchDB restore. The old env copies are temporary rollback material: retain them only until the new admin and Peer checkpoint are independently accepted, then remove the copies from the working rotation directory. Retain a protected copy of the **new** env pair alongside the data/ledger archives after acceptance so that this local recovery point remains usable.

## Stage and switch a matched new pair while both services are stopped

Generate one 256-bit random password as 64 lowercase hex characters in process memory; that alphabet is safe in both the unquoted .env values and CouchDB's docker.ini admin line. Write only the two ignored candidate files, never stdout or shell arguments. Their keys and usernames stay fixed. Use the separate offline verifier before and after atomic per-file replacement. A one-file intermediate state is safe only while both Seller services are stopped; failure requires restoring both old files before starting either service. Keep the candidate directory absent before generation.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
python3 - <<'PY'
import os
import secrets
from pathlib import Path

root = Path(os.environ["ROTATION_DIR"]) / "candidate"
root.mkdir(mode=0o700)
for name in ("couchdb", "peer-couchdb"):
    (root / name).mkdir(mode=0o700)
password = secrets.token_hex(32)
rows = {
    "couchdb/seller.env": f"COUCHDB_USER=supply_seller\nCOUCHDB_PASSWORD={password}\n",
    "peer-couchdb/seller.env": (
        "CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME=supply_seller\n"
        f"CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD={password}\n"
    ),
}
for name, content in rows.items():
    path = root / name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
print("Candidate Seller credential files staged; values withheld")
PY
~~~

Verify the candidate pair before touching the active files:

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
python3 scripts/verify-m2-seller-couchdb-rotation.py \
  --before-root .secrets --after-root "$ROTATION_DIR/candidate"
~~~

Prepare two mode-0600 replacement files while both services are stopped:

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
test ! -e .secrets/couchdb/seller.env.new
test ! -e .secrets/peer-couchdb/seller.env.new
install -m 600 "$ROTATION_DIR/candidate/couchdb/seller.env" .secrets/couchdb/seller.env.new
install -m 600 "$ROTATION_DIR/candidate/peer-couchdb/seller.env" .secrets/peer-couchdb/seller.env.new
~~~

Activate each file as an independent recorded step; a failure leaves both services stopped and requires rollback before either is started:

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
mv .secrets/couchdb/seller.env.new .secrets/couchdb/seller.env
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
mv .secrets/peer-couchdb/seller.env.new .secrets/peer-couchdb/seller.env
~~~

Verify the active new pair, old rendered YAML and old main's node configuration before starting CouchDB:

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
python3 scripts/verify-m2-seller-couchdb-rotation.py \
  --before-root "$ROTATION_DIR/old-secrets" --after-root .secrets
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
make verify-m2-nodes
~~~

Require the new pair to differ from old, match internally, retain 0600/0700 and pass current main's M2 node verifier with the **old** rendered Peer YAML unchanged. Do not run prepare-m2-nodes, which could attempt to replace or compare unrelated configs. No new password or raw env file goes in a log. Recheck the six env filenames and Buyer/Carrier file hashes: only the two Seller files may change.

## Recreate CouchDB first, then Seller Peer

Run each native Compose command separately with --no-deps and --force-recreate. This retains the named data and ledger volumes. A mere restart would keep old container env/admin config. Do not touch Buyer/Carrier or any Orderer.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate couchdb0-seller
~~~

Require CouchDB running, a new container ID, the same named data volume Name/CreatedAt and pinned image, only supply-seller network, and no host-published port. Run two **separate** short-lived probes from supply-seller using the exact command below: first bind .secrets/couchdb/seller.env as /run/supply/admin.env and require HTTP 200, then bind the archived old-secrets/couchdb/seller.env at that path and require HTTP 401 or 403. The endpoint is admin-only; /_up alone would not prove admin authentication. The shell reads the password from the mounted 0600 file and pipes curl configuration over stdin, so the value is absent from argv, command files and logs. Capture only the numeric HTTP code; no verbose trace, response body, headers or cookies.

First run the same safe runtime checker with only the CouchDB component, since Seller Peer is still stopped:

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
python3 scripts/verify-m2-seller-couchdb-runtime.py --component couchdb
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.secrets/couchdb/seller.env,dst=/run/supply/admin.env,readonly" \
  --entrypoint bash supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu '
    set -o pipefail
    set +x
    . /run/supply/admin.env
    printf "user = \"%s:%s\"\n" "$COUCHDB_USER" "$COUCHDB_PASSWORD" |
      curl --config - --silent --show-error --output /dev/null \
        --write-out "%{http_code}\n" \
        http://couchdb0.seller.supply.test:5984/_node/_local/_config/admins
  '
~~~

The new-credential probe must have process exit 0 **and** a log containing only HTTP 200. Run the old-credential probe as its own command/log/exit triad:

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/$ROTATION_DIR/old-secrets/couchdb/seller.env,dst=/run/supply/admin.env,readonly" \
  --entrypoint bash supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu '
    set -o pipefail
    set +x
    . /run/supply/admin.env
    printf "user = \"%s:%s\"\n" "$COUCHDB_USER" "$COUCHDB_PASSWORD" |
      curl --config - --silent --show-error --output /dev/null \
        --write-out "%{http_code}\n" \
        http://couchdb0.seller.supply.test:5984/_node/_local/_config/admins
  '
~~~

The old-credential probe must have process exit 0 and only HTTP 401 or 403 in its log. If either actual HTTP result differs, stop here and use rollback. Preserve sanitized CouchDB startup logs under the ignored directory, but do not copy admin config into evidence. The [CouchDB authentication API](https://docs.couchdb.org/en/stable/api/server/authn.html) distinguishes unauthorized credentials; the [admin config endpoint](https://docs.couchdb.org/en/stable/config/auth.html) requires an administrator.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-seller
~~~

Require Seller Peer running with a new ID, the same named ledger volume Name/CreatedAt, exact old core.yaml SHA, own MSP/TLS/builder binds, only supply-fabric plus supply-seller networks, and effective CouchDB env matching the new files **without printing it**. Make verify-m2-nodes, verify-m1 and network-config must pass on this still-pre-Discovery main. Repeat Seller's own-client TLS and operations /healthz probe, then the two separate native list/getinfo commands from m2-peer-client-mtls.md. Record actual exits, existing supplychannel, height/currentBlockHash and compare with the pre-rotation observation; no new block delivery or governance update is implied. Check the original block artifact SHA and three Orderer/Buyer/Carrier Peer/DB IDs and all nine volume identities again.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
python3 scripts/verify-m2-seller-couchdb-runtime.py --component both
~~~

Only after this checkpoint is independently accepted, record a fresh six-env SHA manifest (inside ignored 0600 evidence), nine-container and nine-volume baseline, M1/lock/source commit, old rendered YAML hash and Seller height/hash for #16 to consume. Retain the candidate pair as the protected new-env backup with the controlled volume archives; compare it byte-for-byte with the active new pair and keep all four files mode 0600. Remove the temporary old env copies from the working rotation directory with separate guarded rm commands after acceptance; do not print their contents. Existing host backups or tool transcripts are outside this working-directory cleanup. The exposed old password must no longer authenticate. #16 then rebases its static patch on this main and starts its Discovery-only staging from the new baseline.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
cmp -s "$ROTATION_DIR/candidate/couchdb/seller.env" .secrets/couchdb/seller.env
cmp -s "$ROTATION_DIR/candidate/peer-couchdb/seller.env" .secrets/peer-couchdb/seller.env
rm -- "$ROTATION_DIR/old-secrets/couchdb/seller.env"
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test ! -e "$ROTATION_DIR/old-secrets/couchdb/seller.env"
rm -- "$ROTATION_DIR/old-secrets/peer-couchdb/seller.env"
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
rmdir "$ROTATION_DIR/old-secrets/couchdb" "$ROTATION_DIR/old-secrets/peer-couchdb" "$ROTATION_DIR/old-secrets"
printf '%s\n' "$ROTATION_DIR" > "$ROTATION_DIR/run-path.txt"
~~~

As the final accepted cleanup step, remove only the active marker; the private run directory and its run-path record remain for audit. The marker's removal lets a later, separately reviewed rotation create a new run.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
rm -- .runtime/m2-seller-couchdb-rotation-active
~~~

## Failure and rollback gate

Before either active .secrets/seller.env file is replaced, a failure leaves the original active pair intact. This includes failure while old-secrets is incomplete, during either volume export, or while generating/verifying the candidate. **Do not attempt to restore nonexistent old-secrets copies.** If preflight fails before `backup/env.before.sha256` exists, neither service has been stopped: leave both running and abort. After that manifest exists, inspect the actual stopped states. If only Seller Peer was stopped, skip the CouchDB-start block below and start that existing Peer after verifying CouchDB is still running; if both were stopped, start the existing CouchDB container first and then the existing Peer. Each start is a separate native command/log/exit and must be followed by its own running/health gate. The original container env still carries the original pair. Any incomplete .env.new file remains unused; remove it only after the recovery checkpoint is reviewed.

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
shasum -a 256 -c "$ROTATION_DIR/backup/env.before.sha256" > /dev/null
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca start couchdb0-seller
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
shasum -a 256 -c "$ROTATION_DIR/backup/env.before.sha256" > /dev/null
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = running
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca start peer0-seller
~~~

Once either active env file has been replaced, old-secrets must be complete and both Seller services must remain stopped. A failure at that point requires restoring both archived env files. On a CouchDB new-admin or old-admin-negative failure, stop Seller Peer if it was inadvertently started, stop Seller CouchDB, restore both old files, and force-recreate CouchDB then Peer. On a Peer failure with the new admin already verified, first inspect its sanitized failure phase while leaving DB at the new password; the old core.yaml was not changed in this gate. If Peer cannot be restored promptly with that unchanged config/new pair, restore both old env files and recreate DB then Peer.

The rollback's individual native steps use the same Compose prefix and probe forms above; retain fresh command/log/exit files for each. Restore the old pair only while both Seller services are stopped:

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca stop peer0-seller
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca stop couchdb0-seller
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
shasum -a 256 -c "$ROTATION_DIR/backup/checksums.sha256" > /dev/null
test ! -e .secrets/couchdb/seller.env.rollback
test ! -e .secrets/peer-couchdb/seller.env.rollback
install -m 600 "$ROTATION_DIR/old-secrets/couchdb/seller.env" .secrets/couchdb/seller.env.rollback
install -m 600 "$ROTATION_DIR/old-secrets/peer-couchdb/seller.env" .secrets/peer-couchdb/seller.env.rollback
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
mv .secrets/couchdb/seller.env.rollback .secrets/couchdb/seller.env
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
test "$(docker inspect --format '{{.State.Status}}' supplyledger-peer0-seller-1)" = exited
test "$(docker inspect --format '{{.State.Status}}' supplyledger-couchdb0-seller-1)" = exited
mv .secrets/peer-couchdb/seller.env.rollback .secrets/peer-couchdb/seller.env
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
if test -f "$ROTATION_DIR/candidate/couchdb/seller.env" &&
   test -f "$ROTATION_DIR/candidate/peer-couchdb/seller.env"; then
  python3 scripts/verify-m2-seller-couchdb-rotation.py \
    --before-root "$ROTATION_DIR/candidate" --after-root .secrets
else
  cmp -s "$ROTATION_DIR/old-secrets/couchdb/seller.env" .secrets/couchdb/seller.env
  cmp -s "$ROTATION_DIR/old-secrets/peer-couchdb/seller.env" .secrets/peer-couchdb/seller.env
fi
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
make verify-m2-nodes
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate couchdb0-seller
~~~

~~~sh
source scripts/m2-seller-couchdb-rotation-state.sh
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-seller
~~~

The rollback verification branch compares with old-secrets if candidate generation never completed; otherwise it verifies the new/old pair distinction. Verify old-admin positive, new-admin negative (when a complete candidate exists), Seller operations/list/getinfo and volume identities. Do not restore data/ledger archives unless actual volume corruption is established and separately reviewed; restoring them can discard later state. Keep all failed native outputs and mark M2-SELLER-CDB-ROT-01 **FAIL**, not PASS.

The later #16 Discovery-only migration has a different rollback boundary: after this password gate passes, a Discovery Peer-start failure should first roll back only its YAML/Peer container and retain the new CouchDB password. Do not conflate the two stages.

## §19.1 evidence template

| Field | Required actual observation |
| --- | --- |
| Test/verdict | M2-SELLER-CDB-ROT-01: PASS, FAIL or NOT RUN; separate #16 and #18 tests remain independently judged |
| Source/versions | Reviewed commit, versions.lock.yaml SHA, locked tool/CouchDB/Peer image descriptors, Compose tier |
| Before state | M1 check, original block artifact SHA and recorded header hash, Seller list/getinfo height/hash, nine IDs and volume Name/CreatedAt, old YAML and six-env file fingerprints |
| Native sequence | UTC and individual command/log/exit for stop Peer, stop CouchDB, two read-only volume exports, stage/verify/switch pair, DB recreate, new/old admin probes, Peer recreate, TLS/health/list/getinfo |
| Actual result | New admin-only HTTP 200, old admin-only HTTP 401/403, preserved volumes, Seller channel height/hash, unchanged other seven node IDs, no leaked values |
| Failure/rollback | Exact failed phase, whether old pair restored, actual DB/Peer/volume state; do not invent txId or validation code |
| Scope | Local Seller cold-state recovery point only; SPEC §16.4 full backup/restore and T-OPS-08 remain NOT RUN |

Live rotation and all its expected responses are **NOT RUN** until this runbook, its offline checker and the current-state preflight receive independent review.
