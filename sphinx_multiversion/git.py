# -*- coding: utf-8 -*-
import collections
import datetime
import logging
import os
import re
import subprocess
import tarfile
import tempfile

GitRef = collections.namedtuple(
    "VersionRef",
    [
        "name",
        "commit",
        "source",
        "is_remote",
        "refname",
        "creatordate",
    ],
)

logger = logging.getLogger(__name__)


def get_toplevel_path(cwd=None):
    cmd = (
        "git",
        "rev-parse",
        "--show-toplevel",
        "--show-superproject-working-tree",
    )
    output = subprocess.check_output(cmd, cwd=cwd).decode()
    # If this is a git submodule of a super project then we'll have two lines
    # of output, otherwise one. Since the superproject flag is second in the
    # command above the superproject will always be the last line if present.
    return output.split()[-1]


def get_current_submodule_commit(sourcedir, cwd=None):
    cmd = (
        "git",
        "ls-tree",
        "HEAD",
        str(sourcedir),
    )
    output = subprocess.check_output(cmd, cwd=cwd).decode()
    return output.split()[2]


def submodule_exists(gitroot, refname, sourcedir, current_submodule_commit):
    cmd = (
        "git",
        "ls-tree",
        refname,
        sourcedir,
    )

    output = subprocess.check_output(cmd, cwd=gitroot).decode()

    if not output:
        return False

    return output.split()[2] == current_submodule_commit


def get_all_refs(gitroot):
    cmd = (
        "git",
        "for-each-ref",
        "--format",
        "%(objectname)\t%(refname)\t%(creatordate:iso)",
        "refs",
    )
    output = subprocess.check_output(cmd, cwd=gitroot).decode()
    for line in output.splitlines():
        is_remote = False
        fields = line.strip().split("\t")
        if len(fields) != 3:
            continue

        commit = fields[0]
        refname = fields[1]
        creatordate = datetime.datetime.strptime(
            fields[2], "%Y-%m-%d %H:%M:%S %z"
        )

        # Parse refname
        matchobj = re.match(
            r"^refs/(heads|tags|remotes/[^/]+)/(\S+)$", refname
        )
        if not matchobj:
            continue
        source = matchobj.group(1)
        name = matchobj.group(2)

        if source.startswith("remotes/"):
            is_remote = True

        yield GitRef(name, commit, source, is_remote, refname, creatordate)


def get_refs(
    gitroot,
    tag_whitelist,
    branch_whitelist,
    remote_whitelist,
    current_submodule_commit,
    sourcedir,
):
    for ref in get_all_refs(gitroot):
        if ref.source == "tags":
            if tag_whitelist is None or not re.match(tag_whitelist, ref.name):
                logger.debug(
                    "Skipping '%s' because tag '%s' doesn't match the "
                    "whitelist pattern",
                    ref.refname,
                    ref.name,
                )
                continue
        elif ref.source == "heads":
            if branch_whitelist is None or not re.match(
                branch_whitelist, ref.name
            ):
                logger.debug(
                    "Skipping '%s' because branch '%s' doesn't match the "
                    "whitelist pattern",
                    ref.refname,
                    ref.name,
                )
                continue
        elif ref.is_remote and remote_whitelist is not None:
            remote_name = ref.source.partition("/")[2]
            if not re.match(remote_whitelist, remote_name):
                logger.debug(
                    "Skipping '%s' because remote '%s' doesn't match the "
                    "whitelist pattern",
                    ref.refname,
                    remote_name,
                )
                continue
            if branch_whitelist is None or not re.match(
                branch_whitelist, ref.name
            ):
                logger.debug(
                    "Skipping '%s' because branch '%s' doesn't match the "
                    "whitelist pattern",
                    ref.refname,
                    ref.name,
                )
                continue
        else:
            logger.debug(
                "Skipping '%s' because its not a branch or tag", ref.refname
            )
            continue

        if not submodule_exists(
            gitroot=gitroot,
            refname=ref.refname,
            sourcedir=sourcedir,
            current_submodule_commit=current_submodule_commit,
        ):
            logger.debug(
                f"Skipping {ref.refname} because there are no the {sourcedir} "
                f"with the commit {current_submodule_commit}"
            )
            continue

        yield ref


def file_exists(gitroot, refname, filename):
    if os.sep != "/":
        # Git requires / path sep, make sure we use that
        filename = filename.replace(os.sep, "/")

    cmd = (
        "git",
        "cat-file",
        "-e",
        "{}:{}".format(refname, filename),
    )
    proc = subprocess.run(
        cmd, cwd=gitroot, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return proc.returncode == 0


def copy_tree(
    gitroot, dst, reference, sourcedir, submodule_tar_path, sourcepath="."
):
    with tempfile.SpooledTemporaryFile() as fp:
        cmd = (
            "git",
            "archive",
            "--format",
            "tar",
            reference.commit,
            "--",
            sourcepath,
        )
        subprocess.check_call(cmd, cwd=gitroot, stdout=fp)
        fp.seek(0)
        with tarfile.TarFile(fileobj=fp) as tarfp:
            tarfp.extractall(dst)

        with tarfile.open(submodule_tar_path, "r") as tarfp:
            tarfp.extractall(dst + f"/{sourcedir}")


def copy_submodule(submodule_path, output_path, submodule_commit):
    cmd = (
        "git",
        "archive",
        "--format",
        "tar",
        "-o",
        output_path,
        submodule_commit,
    )
    subprocess.run(cmd, cwd=submodule_path)
