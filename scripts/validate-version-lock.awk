# versions.lock.yaml uses two-space mappings and scalar lists. Reject other YAML forms
# so verify-m0's path lookup cannot disagree with a general YAML reader.
function fail(reason) {
  printf "invalid version lock at line %d: %s\n", NR, reason > "/dev/stderr"
  invalid = 1
  exit 1
}

function scalar(value, first) {
  if (value == "" || value ~ /^ / || value ~ / $/) fail("empty or padded scalar")
  if (value ~ /^"/) {
    if (value !~ /^"[^"\\]*"$/) fail("unsupported quoted scalar")
    return
  }
  first = substr(value, 1, 1)
  if (value ~ /^[0-9]+\.[0-9]+$/) fail("quote decimal-like scalar to preserve version text")
  if (index("-?:!&*|>{[,'\"%@`", first) || index(value, "\"") ||
      index(value, "'") || index(value, "\\") || value ~ /[{}\[\]]/ ||
      value ~ /: / || value ~ /:$/ || value ~ /(^| )#/) {
    fail("unsupported plain scalar")
  }
}

BEGIN {
  previous_depth = -1
  container[0] = "map"
}

{
  if ($0 ~ /\t|\r/ || $0 ~ /[ ]$/) fail("tab, carriage return, or trailing space")
  if ($0 == "") next
  match($0, /^ */)
  spaces = RLENGTH
  if (spaces % 2) fail("indentation is not a multiple of two")
  depth = spaces / 2
  entry = substr($0, spaces + 1)
  if (entry ~ /^#|^---$|^\.\.\.$/) fail("unsupported YAML document or comment")

  if (previous_depth < 0) {
    if (depth != 0) fail("root must begin at column one")
  } else if (depth > previous_depth) {
    if (depth != previous_depth + 1 || !awaiting) fail("unexpected child indentation")
    container[depth] = entry ~ /^- / ? "list" : "map"
  } else {
    if (awaiting) fail("mapping key has no child")
    for (i = depth + 1; i <= previous_depth; i++) {
      delete container[i]
      delete path[i]
    }
    if (!(depth in container)) fail("dedent has no parent")
  }

  if (entry ~ /^- /) {
    if (container[depth] != "list") fail("list item in mapping")
    scalar(substr(entry, 3))
    awaiting = 0
  } else {
    if (container[depth] != "map") fail("mapping key in scalar list")
    colon = index(entry, ":")
    if (!colon) fail("mapping colon is missing")
    key = substr(entry, 1, colon - 1)
    if (key !~ /^[A-Za-z][A-Za-z0-9_-]*$/) fail("unsupported mapping key")
    tail = substr(entry, colon + 1)
    if (tail != "" && tail !~ /^ [^ ]/) fail("mapping value needs one space")
    path[depth] = key
    full_path = path[0]
    for (i = 1; i <= depth; i++) full_path = full_path "." path[i]
    if (full_path in seen) fail("duplicate key path " full_path)
    seen[full_path] = 1
    if (tail == "") {
      awaiting = 1
    } else {
      scalar(substr(tail, 2))
      awaiting = 0
    }
  }
  previous_depth = depth
  records++
}

END {
  if (invalid) exit 1
  if (!records || awaiting) {
    print "invalid version lock: empty document or mapping key has no child" > "/dev/stderr"
    exit 1
  }
}
