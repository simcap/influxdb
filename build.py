#!/usr/bin/env python2.7

import sys
import os
import subprocess
import time
import datetime
import shutil

# PACKAGING VARIABLES
INSTALL_ROOT_DIR = "/usr/bin"
LOG_DIR = "/var/log/influxdb"
DATA_DIR = "/var/lib/influxdb"
SCRIPT_DIR = "/usr/lib/influxdb/scripts"
CONFIG_DIR = "/etc/influxdb"
LOGROTATE_DIR = "/etc/logrotate.d"

INIT_SCRIPT = "scripts/init.sh"
SYSTEMD_SCRIPT = "scripts/influxdb.service"
POSTINST_SCRIPT = "scripts/post-install.sh"
LOGROTATE_SCRIPT = "scripts/logrotate"
CONFIG_SAMPLE = "etc/config.sample.toml"
PREINST_SCRIPT = None

# META-PACKAGE VARIABLES
PACKAGE_LICENSE = "MIT"
PACKAGE_URL = "influxdata.com"
MAINTAINER = "support@influxdata.com"
VENDOR = "InfluxData"
DESCRIPTION = "A distributed time-series database"

# SCRIPT START
prereqs = [ 'git', 'go' ]
optional_prereqs = [ 'gvm', 'fpm', 'awscmd', 'rpmbuild' ]

fpm_common_args = "-s dir --log error  --vendor {} --url {} --after-install {} --license {} --maintainer {} --name influxdb --config-files {} --config-files {} --description \"{}\"".format(VENDOR, PACKAGE_URL, POSTINST_SCRIPT, PACKAGE_LICENSE, MAINTAINER, CONFIG_DIR, LOGROTATE_DIR, DESCRIPTION)

targets = {
    'influx' : './cmd/influx/main.go',
    'influxd' : './cmd/influxd/main.go',
    'influx_stress' : './cmd/influx_stress/influx_stress.go',
    'influx_inspect' : './cmd/influx_inspect/*.go',
}

supported_platforms = [ 'darwin', 'windows', 'linux' ]
supported_archs = [ 'amd64', '386', 'arm' ]
supported_go = [ '1.5.1' ]
supported_packages = {
    "darwin": [ "tar", "zip" ],
    "linux": [ "deb", "rpm", "tar.gz", "zip" ],
    "windows": [ "tar", "zip" ],
}

def run(command, allow_failure=False, shell=False):
    out = None
    try:
        if shell:
            out = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=shell)
        else:
            out = subprocess.check_output(command.split(), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print ""
        print "Executed command failed!"
        print "-- Command run was: {}".format(command)
        print "-- Failure was: {}".format(e)
        if allow_failure:
            print "Continuing..."
            return out
        else:
            print ""
            print "Stopping."
            sys.exit(1)
    except OSError as e:
        print ""
        print "Invalid command!"
        print "-- Command run was: {}".format(command)
        print "-- Failure was: {}".format(e)
        if allow_failure:
            print "Continuing..."
            return out
        else:
            print ""
            print "Stopping."
            sys.exit(1)
    else:
        return out

def create_temp_dir():
    command = "mktemp -d /tmp/tmp.XXXXXXXX"
    out = run(command)
    return out.strip()

def get_current_commit(short=False):
    command = None
    if short:
        command = "git log --pretty=format:'%h' -n 1"
    else:
        command = "git rev-parse HEAD"
    out = run(command)
    return out.strip('\'\n\r ')

def get_current_branch():
    command = "git rev-parse --abbrev-ref HEAD"
    out = run(command)
    return out.strip()

def get_system_arch():
    return os.uname()[4]

def get_system_platform():
    if sys.platform.startswith("linux"):
        return "linux"
    else:
        return sys.platform

def check_path_for(b):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    
    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        full_path = os.path.join(path, b)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path

def check_environ(build_dir = None):
    print "\nChecking environment:"
    for v in [ "GOPATH", "GOBIN" ]:
        print "\t- {} -> {}".format(v, os.environ.get(v))
    
    cwd = os.getcwd()
    if build_dir == None and os.environ.get("GOPATH") not in cwd:
        print "\n!! WARNING: Your current directory is not under your GOPATH! This probably won't work."

def check_prereqs():
    print "\nChecking for dependencies:"
    for req in prereqs:
        print "\t- {} ->".format(req),
        path = check_path_for(req)
        if path:
            print "{}".format(path)
        else:
            print "?"
    for req in optional_prereqs:
        print "\t- {} (optional) ->".format(req),
        path = check_path_for(req)
        if path:
            print "{}".format(path)
        else:
            print "?"
    print ""

def build(version=None,
          branch=None,
          commit=None,
          platform=None,
          arch=None,
          nightly=False,
          nightly_version=None,
          rc=None,
          race=False):
    print "Building for..."
    print "\t- version: {}".format(version)
    if rc:
        print "\t- release candidate: {}".format(rc)
    print "\t- commit: {}".format(commit)
    print "\t- branch: {}".format(branch)
    print "\t- platform: {}".format(platform)
    print "\t- arch: {}".format(arch)
    print "\t- nightly? {}".format(str(nightly).lower())
    print "\t- race enabled? {}".format(str(race).lower())
    print ""

    if rc:
        # If a release candidate, update the version information accordingly
        version = "{}rc{}".format(version, rc)
    
    get_command = "go get -d ./..."
    checkout_command = "git checkout {}".format(commit)
    make_command = "make dist OS_ARCH={}/{} VERSION={} NIGHTLY={}".format(platform,
                                                                          arch,
                                                                          version,
                                                                          str(nightly).lower())    
    print "Starting build..."
    for b, c in targets.iteritems():
        print "\t- Building '{}'...".format(b),
        build_command = ""
        build_command += "GOOS={} GOOARCH={} ".format(platform, arch)
        build_command += "go build -o {} ".format(b)
        # Receiving errors when including the race flag. Skipping for now.
        # if race:
        #     build_command += "-race "
        build_command += "-ldflags=\"-X main.buildTime='{}' ".format(datetime.datetime.utcnow().isoformat())
        build_command += "-X main.version={} ".format(version)
        build_command += "-X main.branch={} ".format(branch)
        build_command += "-X main.commit={}\" ".format(get_current_commit())
        build_command += c
        out = run(build_command, shell=True)
        print "[ DONE ]"
    print ""

def create_dir(path):
    try:
        os.makedirs(path)
    except OSError as e:
        print e

def move_file(fr, to):
    try:
        os.rename(fr, to)
    except OSError as e:
        print e

def create_package_fs(build_root):
    print "\t- Creating a filesystem hierarchy from directory: {}".format(build_root)
    # Using [1:] for the path names due to them being absolute
    create_dir(os.path.join(build_root, INSTALL_ROOT_DIR[1:]))
    create_dir(os.path.join(build_root, LOG_DIR[1:]))
    create_dir(os.path.join(build_root, DATA_DIR[1:]))
    create_dir(os.path.join(build_root, SCRIPT_DIR[1:]))
    create_dir(os.path.join(build_root, CONFIG_DIR[1:]))
    create_dir(os.path.join(build_root, LOGROTATE_DIR[1:]))

def package_scripts(build_root):
    print "\t- Copying scripts and sample configuration to build directory"
    shutil.copyfile(INIT_SCRIPT, os.path.join(build_root, SCRIPT_DIR[1:], INIT_SCRIPT.split('/')[1]))
    shutil.copyfile(SYSTEMD_SCRIPT, os.path.join(build_root, SCRIPT_DIR[1:], SYSTEMD_SCRIPT.split('/')[1]))
    shutil.copyfile(LOGROTATE_SCRIPT, os.path.join(build_root, SCRIPT_DIR[1:], LOGROTATE_SCRIPT.split('/')[1]))
    shutil.copyfile(CONFIG_SAMPLE, os.path.join(build_root, CONFIG_DIR[1:], CONFIG_SAMPLE.split('/')[1]))
    
def build_packages(build_output, version):
    TMP_BUILD_DIR = create_temp_dir()
    print "Packaging..."
    for p in build_output:
        create_dir(os.path.join(TMP_BUILD_DIR, p))
        for a in build_output[p]:
            BUILD_ROOT = os.path.join(TMP_BUILD_DIR, p, a)
            create_dir(BUILD_ROOT)
            create_package_fs(BUILD_ROOT)
            package_scripts(BUILD_ROOT)
            current_location = build_output[p][a]
            for b in targets:
                fr = os.path.join(current_location, b)
                to = os.path.join(BUILD_ROOT, INSTALL_ROOT_DIR[1:], b)
                print "\t- [{}][{}] - Moving from '{}' to '{}'".format(p, a, fr, to)
                move_file(fr, to)
            for package_type in supported_packages[p]:
                print "\t- Packaging directory '{}' as '{}'...".format(BUILD_ROOT, package_type),
                fpm_command = "fpm {} -t {} --version {} -C {}".format(fpm_common_args,
                                                                       package_type,
                                                                       version,
                                                                       BUILD_ROOT)
                out = run(fpm_command, shell=True)
                print "[ DONE ]"
    print ""
    
def main():
    print ""
    print "--- InfluxDB Builder ---"

    check_environ()
    check_prereqs()
    
    commit = None
    target_platform = None
    target_arch = None
    nightly = False
    race = False
    nightly_version = None
    branch = None
    version = "0.9.5"
    rc = None
    package = False
    
    for arg in sys.argv:
        if '--outdir' in arg:
            # Output directory. If none is specified, then builds will be placed in the same directory.
            output_dir = arg.split("=")[1]
        if '--commit' in arg:
            # Commit to build from. If none is specified, then it will build from the most recent commit.
            commit = arg.split("=")[1]
        if '--branch' in arg:
            # Branch to build from. If none is specified, then it will build from the current branch.
            branch = arg.split("=")[1]
        elif '--arch' in arg:
            # Target architecture. If none is specified, then it will build for the current arch.
            target_arch = arg.split("=")[1]
        elif '--platform' in arg:
            # Target platform. If none is specified, then it will build for the current platform.
            target_platform = arg.split("=")[1]
        elif '--version' in arg:
            # Version to assign to this build (0.9.5, etc)
            version = arg.split("=")[1]
        elif '--rc' in arg:
            # Signifies that this is a release candidate build.
            rc = arg.split("=")[1]
        elif '--race' in arg:
            # Signifies that race detection should be enabled.
            race = True
        elif '--package' in arg:
            # Signifies that race detection should be enabled.
            package = True
        elif '--nightly' in arg:
            # Signifies that this is a nightly build.
            nightly = True
            # In order to support nightly builds on the repository, we are adding the epoch timestamp
            # to the version so that seamless upgrades are possible.
            if len(version) <= 5:
                version = "{}.0.n{}".format(version, int(time.time()))
            else:
                version = "{}.n{}".format(version, int(time.time()))
        else:
            print "!! Unknown argument: {}".format(arg)
            sys.exit(1)

    if nightly and rc:
        print "!! Cannot be both nightly and a release candidate! Stopping."
        sys.exit(1)
            
    if not commit:
        commit = get_current_commit(short=True)
    if not branch:
        branch = get_current_branch()
    if not target_arch:
        target_arch = get_system_arch()
    if not target_platform:
        target_platform = get_system_platform()

    if target_arch == "x86_64":
        target_arch = "amd64"

    build_output = {}
    # TODO(rossmcdonald): Prepare git repo for build (checking out correct branch/commit, etc.)
    # prepare(branch=branch, commit=commit)
    if target_platform == 'all' or target_arch == 'all':
        # Create multiple builds
        pass
    else:
        # Create single build
        build(version=version,
              branch=branch,
              commit=commit,
              platform=target_platform,
              arch=target_arch,
              nightly=nightly,
              nightly_version=nightly_version,
              rc=rc,
              race=race)
        build_output.update( { target_platform : { target_arch : '.' } } )

    if package:
        if not check_path_for("fpm"):
            print "!! Cannot package without command 'fpm'. Stopping."
            sys.exit(1)
        build_packages(build_output, version)

if __name__ == '__main__':
    main()
