#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Mechanical checks for a hand-written XRD schema.

Usage:
    python3 check_xrd_schema.py apis/*/definition.yaml
    python3 check_xrd_schema.py --min-corpus 3 apis/tiny/definition.yaml

Collisions, allowlist casing, group stutter, enum casing, missing descriptions,
unbounded lists and printer columns Crossplane already appends are all greppable
out of the YAML, before any cluster is involved. Everything this reports is
cheap to fix before the first version ships and impossible to fix afterwards,
because two XRD versions are two views of one stored object.

One trap sits underneath all of it: a check whose corpus is empty reports every
schema clean. The corpus is asserted before the verdict is trusted, and
extraction failure exits with a different code than a finding.

Exit codes, per the repo convention:

    0   clean
    10  validation failure -- at least one finding
    2   not found / extraction broken -- no files matched, PyYAML missing, or a
        corpus too small to have been extracted correctly. NOT a clean pass.

Casing is checked on two surfaces with different rules:

  * A FIELD is lowerCamel with the initialism title-cased, never canonicalised:
    vpcId, projectId, bucketArn, cacheTtlSeconds. This is not the Kubernetes
    core convention (containerID, imageID) and deliberately so: across the
    Crossplane resources a user sees beside an XR the field surface is
    title-case throughout, and `vpcID` next to `vpcId` is one concept with two
    spellings.

  * A KIND carries the initialism in full: VPC, DNSRecord, OIDCProvider,
    HTTPLoadBalancer. The Kind is the GVK and spec.names.kind, so unlike a
    field it cannot be renamed after release without making every stored
    object unreadable. It is the one name worth getting right up front.

The ACRONYMS allowlist therefore applies to the KIND only. Fields are checked
registry-free: under the field convention no word is ever all-caps, so any
all-caps run of two or more letters is a defect without needing a table, and a
token missing from the table is a missed defect rather than a false alarm.

What this reports as REVIEW rather than FAIL, because the call is semantic:

  * Group stutter. `artifactoryRepositoryName` restates the object's own
    identity and wants to be `name`; `gatewayName` on a Route names a DIFFERENT
    object that carries the group's word, and renaming it to `name` is worse.
    Both shapes are prefix-anchored matches on the group.
  * Booleans, and strings with no enum, pattern, maxLength or format.

What it does not look at all, and why it does not try:

  * Kind stutter. `repositoryClass` is a good name and `repositoryName` is not,
    and the difference is semantic. A check that fires on both pushes someone to
    break the good one.
  * Which fields are identity fields needing `self == oldSelf`.
  * Whether a `pattern` matches what the backend actually enforces.

Those stay review judgements. See `charter/xrd-design.md`.
"""

from __future__ import annotations

import argparse
import glob
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by the dependency check test
    print(
        "ERROR: PyYAML is not installed, so no schema could be read. This is an "
        "extraction failure, not a clean pass.\n"
        "       pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(2)  # not found

EXIT_CLEAN = 0
EXIT_FINDINGS = 10  # validation failure
EXIT_NO_CORPUS = 2  # not found

# ---------------------------------------------------------------------------
# KIND casing only. A Kind carries its initialism in full (VPC, DNSRecord,
# OIDCProvider), and it is the one name that cannot be renamed after release.
# Fields are NOT checked against this table -- the field surface is title-case
# (vpcId, bucketArn) and is checked registry-free below.
#
# ALLOWLIST, not a registry. A gap here is a missed defect, never a false
# alarm -- that inversion is the whole reason this shape works. A registry of
# canonical initialisms, used the other way round to decide what casing is
# wrong, fires on every name it does not know, so nearly every hit is a gap in
# the registry rather than a defect, and the check gets switched off.
#
# Every entry carries the expansion it stands for; an entry nobody can expand
# does not belong. Trim this to the acronyms your API actually uses, and add to
# it only with the expansion written down.
# ---------------------------------------------------------------------------
ACRONYMS = {
    "Api": "API",     # Application Programming Interface
    "Acl": "ACL",     # Access Control List
    "Arn": "ARN",     # Amazon Resource Name
    "Ca": "CA",       # Certificate Authority
    "Cidr": "CIDR",   # Classless Inter-Domain Routing
    "Cpu": "CPU",     # Central Processing Unit
    "Csi": "CSI",     # Container Storage Interface
    "Db": "DB",       # Database
    "Dns": "DNS",     # Domain Name System
    "Fqdn": "FQDN",   # Fully Qualified Domain Name
    "Http": "HTTP",   # HyperText Transfer Protocol
    "Https": "HTTPS", # HyperText Transfer Protocol Secure
    "Id": "ID",       # Identifier
    "Ip": "IP",       # Internet Protocol
    "Jwt": "JWT",     # JSON Web Token
    "Oidc": "OIDC",   # OpenID Connect
    "Os": "OS",       # Operating System
    "Ssh": "SSH",     # Secure Shell
    "Tls": "TLS",     # Transport Layer Security
    "Ttl": "TTL",     # Time To Live
    "Uri": "URI",     # Uniform Resource Identifier
    "Url": "URL",     # Uniform Resource Locator
    "Uuid": "UUID",   # Universally Unique Identifier
}

# Enum values that are proper nouns with established casing, where CamelCasing
# produces something wrong (Npm, Pypi). Each one is an exception you are
# choosing; keep the list short and write the reason beside the field.
ENUM_PROPER_NOUNS = {"npm", "PyPI", "NuGet"}

# Crossplane appends these to every XR. Defining one yourself prints it twice.
CROSSPLANE_COLUMNS = {"SYNCED", "READY", "COMPOSITION", "COMPOSITIONREVISION", "AGE"}

# Below this, extraction is broken -- not a clean pass. Override with
# --min-corpus when an API really is this small, so the small corpus is an
# assertion someone made rather than a silence nobody noticed.
DEFAULT_MIN_CORPUS = 5

XRD_KINDS = ("CompositeResourceDefinition", "CustomResourceDefinition")


def split_words(s):
    """Split a camelCase/PascalCase identifier at case-transition boundaries.

    A boundary falls before index i when s[i] is upper and s[i-1] is not (the
    ordinary hump: fooBar -> foo, Bar), or when s[i] and s[i-1] are both upper
    and s[i+1] is lower (the acronym run: HTTPServer -> HTTP, Server). Digits
    never start a word, so Ipv4 stays one word.

    This boundary test is the point: a substring replace reaches inside longer
    words and rewrites apiep (from api_ep) to APIep.
    """
    if not s:
        return []
    words, start, n = [], 0, len(s)
    for i in range(1, n):
        prev_upper, cur_upper = s[i - 1].isupper(), s[i].isupper()
        if not cur_upper:
            continue
        if not prev_upper:
            words.append(s[start:i])
            start = i
            continue
        if i + 1 < n and not s[i + 1].isupper() and s[i + 1].isalnum():
            words.append(s[start:i])
            start = i
    words.append(s[start:])
    return words


def kind_acronym_violations(kind):
    """Title-cased initialisms in a PascalCase Kind: Http -> HTTP.

    A Kind carries its initialism in full (VPC, OIDCProvider, DNSRecord,
    HTTPLoadBalancer), and it is the GVK and spec.names.kind, so it is the one
    name a later release cannot fix. Checked against the allowlist, where a gap
    is a missed defect and never a false alarm.

    Only the token itself is decidable. `HttpLoadbalancer` also has a missing
    word boundary inside `Loadbalancer`, which no table can see.
    """
    out = []
    for w in split_words(kind):
        if w in ACRONYMS:
            out.append((w, ACRONYMS[w]))
    return out


def field_casing_violations(name):
    """All-caps runs in a lowerCamel field name: vpcID -> vpcId.

    The field surface is title-case throughout (vpcId, bucketArn,
    cacheTtlSeconds), so no word in a correct field name is ever all-caps. That makes this registry-free: the check needs no
    table and cannot false-alarm on an ordinary English word or on an acronym
    nobody wrote down.

    A canonicalised field is not a style preference. `vpcID` beside the `vpcId`
    on every resource a user sees next to this XR is one concept with two
    spellings -- the defect this exists to catch.

    Word 0 is skipped: it is lowercase by the lowerCamel convention, and a
    field that does not start lowercase is reported separately. Single letters
    are skipped too, so the `A` in `enableResourceNameDnsARecordOnLaunch` (a
    DNS A record) is left alone.
    """
    out = []
    for i, w in enumerate(split_words(name)):
        if i == 0 or len(w) < 2 or not w.isupper():
            continue
        # Alphabetic only. `S3` and `V3` are already their own title-case form,
        # so flagging them prints a "fix" identical to the input.
        if not w.isalpha():
            continue
        out.append((w, w[0] + w[1:].lower()))
    return out


def walk(node, path, names, findings, review, in_status):
    """Collect every property name and check each node's own schema."""
    if not isinstance(node, dict):
        return

    props = node.get("properties")
    if isinstance(props, dict):
        for k, v in props.items():
            child = f"{path}.{k}"
            names.append((k, child))

            if isinstance(v, dict):
                if not v.get("description"):
                    findings.append(f"{child}: no description")

                t = v.get("type")
                if t == "string" and not any(
                    x in v for x in ("enum", "pattern", "maxLength", "format")
                ):
                    review.append(
                        f"{child}: bare `type: string` -- no enum, pattern, maxLength or format"
                    )
                if t == "boolean" and not in_status:
                    review.append(
                        f"{child}: boolean -- a two-value enum that can never gain a third"
                    )
                if t == "array":
                    if "x-kubernetes-list-type" not in v:
                        findings.append(
                            f"{child}: array with no x-kubernetes-list-type (atomic by default: "
                            "duplicates accepted, server-side apply clobbers)"
                        )
                    if "maxItems" not in v:
                        findings.append(
                            f"{child}: array with no maxItems (CEL cost is budgeted against "
                            "the declared maximum)"
                        )
                # Not style. The API server refuses to create the CRD at all:
                # "uniqueItems cannot be set to true since the runtime
                # complexity becomes quadratic" (apiextensions-apiserver
                # validation.go). It is the obvious way to write "duplicates
                # are rejected", and the correct one is list-type: set.
                if v.get("uniqueItems") is True:
                    findings.append(
                        f"{child}: uniqueItems: true is forbidden in a CRD schema -- the API "
                        "server rejects the whole CRD (\"runtime complexity becomes "
                        "quadratic\"). Use x-kubernetes-list-type: set"
                    )
                for ev in v.get("enum", []) or []:
                    if not isinstance(ev, str) or ev in ENUM_PROPER_NOUNS:
                        continue
                    if not ev[:1].isupper():
                        findings.append(
                            f"{child}: enum value {ev!r} is not CamelCase with an initial capital"
                        )

            walk(v, child, names, findings, review, in_status)

    items = node.get("items")
    if isinstance(items, dict):
        walk(items, f"{path}[]", names, findings, review, in_status)


def check(path):
    """Return (names, findings, review, kind_count) for one YAML file."""
    with open(path, encoding="utf-8") as fh:
        docs = [d for d in yaml.safe_load_all(fh) if isinstance(d, dict)]

    names, findings, review = [], [], []
    kinds = 0

    for d in docs:
        if d.get("kind") not in XRD_KINDS:
            continue
        spec = d.get("spec") or {}
        kind = ((spec.get("names") or {}).get("kind")) or ""
        group = spec.get("group") or ""

        # Names from THIS document only. The stutter check below compares them
        # against this document's group, so a file holding two XRDs must not
        # check the first one's fields against the second one's group --
        # `repositoryClass` under group `artifactory.example.com` is a good
        # name, and reading it beside a second XRD in group
        # `repository.example.com` reported it as stutter.
        doc_names = []

        if kind:
            kinds += 1
            for w, want in kind_acronym_violations(kind):
                findings.append(
                    f"{path}: Kind {kind!r} carries mis-cased acronym {w!r} (want {want!r}). "
                    "A Kind is the GVK and spec.names.kind -- renaming it stops the CRD "
                    "serving the old name and every stored object becomes unreadable. "
                    "This is not a rename you can make later."
                )

        for v in spec.get("versions") or []:
            vn = v.get("name")
            schema = ((v.get("schema") or {}).get("openAPIV3Schema")) or {}
            root = schema.get("properties") or {}
            for section in ("spec", "status"):
                if section in root:
                    walk(
                        root[section],
                        f"{path}[{vn}].{section}",
                        doc_names,
                        findings,
                        review,
                        in_status=(section == "status"),
                    )

            cols = {
                c.get("name", "").upper()
                for c in (v.get("additionalPrinterColumns") or [])
            }
            for dup in sorted(cols & CROSSPLANE_COLUMNS):
                findings.append(
                    f"{path}[{vn}]: printer column {dup} is already appended by Crossplane "
                    "-- it will print twice"
                )

        # Group stutter, checked against the GROUP's first label only,
        # prefix-anchored, and REVIEW rather than FAIL. It cannot tell apart
        # two shapes that look identical:
        #
        #   artifactoryRepositoryName -- restates this object's own identity.
        #                                Real stutter; it wants to be `name`.
        #   gatewayName               -- names a DIFFERENT object that happens
        #                                to carry the group's word. Renaming it
        #                                to `name` is actively worse, because
        #                                `name` no longer says whose.
        #   gatewayTimeoutSeconds     -- a compound term (HTTP 504 Gateway
        #                                Timeout) that begins with the word.
        #
        # The difference is semantic, which is the same reason kind stutter is
        # left to review. Both shapes were produced by an agent on one API.
        stem = group.split(".")[0].lower()
        for n, where in doc_names:
            if stem and n.lower() != stem and n.lower().startswith(stem):
                review.append(
                    f"{where}: field name {n!r} starts with the group {stem!r} -- "
                    f"it reads as {stem}.{kind}.{n}. Stutter if it restates this "
                    f"object's own identity; fine if it names a different object"
                )

        names.extend(doc_names)

    return names, findings, review, kinds


def run(patterns, min_corpus=DEFAULT_MIN_CORPUS, out=None):
    """Check every file matching `patterns`. Returns an exit code."""
    out = out or sys.stdout
    paths = []
    for a in patterns:
        paths.extend(sorted(glob.glob(a)))
    if not paths:
        print(
            "CORPUS ERROR: no files matched -- extraction is broken, not a clean pass",
            file=out,
        )
        return EXIT_NO_CORPUS

    all_names, all_findings, all_review, kinds = [], [], [], 0
    for p in paths:
        names, findings, review, k = check(p)
        all_names.extend(names)
        all_findings.extend(findings)
        all_review.extend(review)
        kinds += k

    # A check whose corpus is empty reports every schema clean. Assert the
    # corpus before trusting the verdict.
    if len(all_names) < min_corpus or kinds == 0:
        print(
            f"CORPUS ERROR: {len(all_names)} field names, {kinds} kinds across "
            f"{len(paths)} file(s) -- extraction is broken, not a clean pass. "
            f"If the API really is this small, pass --min-corpus.",
            file=out,
        )
        return EXIT_NO_CORPUS

    # Naming, checked two ways. Neither subsumes the other.
    #
    # 1. Collision: one concept spelled two ways (projectId / ProjectID).
    #    Registry-free, so no false positive from an ordinary English word.
    #    Blind to an acronym spelled two ways across names that never collide.
    seen = {}
    for n, _ in all_names:
        seen.setdefault(n.lower(), set()).add(n)
    for _, spellings in sorted(seen.items()):
        if len(spellings) > 1:
            all_findings.append(
                f"one concept, two spellings: {' / '.join(sorted(spellings))}"
            )

    # 2. Field casing: an all-caps initialism, which the field surface never
    #    uses. Registry-free, and invisible to (1) when the two spellings live
    #    on different sides of the composition rather than in one schema.
    for n, where in all_names:
        if n[:1].isupper():
            all_findings.append(
                f"{where}: field name {n!r} is not lowerCamel -- it must start lowercase"
            )
        for w, want in field_casing_violations(n):
            # Detection is registry-free; the table only picks the advice. A
            # token nobody can expand is an invented abbreviation, and
            # title-casing it (adminsSG -> adminsSg) answers the casing
            # question while leaving the worse problem in place.
            if w in set(ACRONYMS.values()):
                fix = (
                    f"the field surface is title-case, so write {want!r}. Everything "
                    f"a user sees beside this XR spells it that way"
                )
            else:
                fix = (
                    f"the field surface is title-case, so this is at best {want!r} -- but "
                    f"{w!r} is not an acronym with a written-down expansion, so expand it "
                    f"into a word instead and the casing question disappears"
                )
            all_findings.append(
                f"{where}: field name {n!r} canonicalises {w!r} -- {fix}"
            )

    for f in sorted(set(all_findings)):
        print("FAIL:   " + f, file=out)
    for f in sorted(set(all_review)):
        print("REVIEW: " + f, file=out)
    print(
        f"\ncorpus: {len(all_names)} field names, {kinds} kind(s), {len(paths)} file(s); "
        f"{len(set(all_findings))} failure(s), {len(set(all_review))} to review",
        file=out,
    )
    return EXIT_FINDINGS if all_findings else EXIT_CLEAN


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Mechanical checks for a hand-written XRD schema.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "paths",
        nargs="*",
        default=["apis/*/definition.yaml"],
        metavar="PATH",
        help="XRD files or globs (default: apis/*/definition.yaml)",
    )
    ap.add_argument(
        "--min-corpus",
        type=int,
        default=DEFAULT_MIN_CORPUS,
        metavar="N",
        help=(
            f"fewest field names that count as a real extraction "
            f"(default: {DEFAULT_MIN_CORPUS}). Below it the run is an error, not a pass."
        ),
    )
    args = ap.parse_args(argv)
    return run(args.paths, min_corpus=args.min_corpus)


if __name__ == "__main__":
    sys.exit(main())
