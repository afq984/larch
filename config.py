"""
Configuration file for larch, the lazy Arch Linux installer
"""

# How to configure the mirrorlist
# 'generator': fetch from the mirrorlist generator: https://www.archlinux.org/mirrorlist
# 'static': use a static mirror configured by mirror_static
mirrorlist = 'generator'

# short country code, used by mirrorlist = 'generator'
mirror_country = 'TW'

# the single static mirror used by mirrorlist = 'static'
mirror_static = 'http://10.88.88.49/archlinux/$repo/os/$arch'

# Disk to install Arch Linux on
# The installer always creates a GPT (GUID Partition Table)
# Two partitions will be created:
# UEFI boot: 1GB fat32 /boot (esp) and the remaining space for /
# Legacy boot: 1MB of BIOS boot partition and the remaining space for /
# No swap partitions will be created
disk = '/dev/sda'
disk = '/dev/nvme0n1'
disk = 'FIXME'  # prevents accidents

# Root password
# Set to None to prompt
root_password = None

# Install UEFI or BIOS (as known as Legacy) GRUB Bootloader
use_uefi = True

# Filesystem of the root partition
# Supported choices are ext4, xfs, f2fs, btrfs
root_filesystem = 'xfs'

# Hostname
# Set to None to not set it
hostname = None

# Packages to install
packages = [
    'base', 'base-devel', 'grub', 'python',
    'openssh', 'rsync', 'vim',
    'intel-ucode',
]

# Services to enable
services = [
    'systemd-timesyncd',
]

# We need efibootmgr for UEFI GRUB
if use_uefi:
    packages.append('efibootmgr')
# corresponding filesystem tools
if root_filesystem == 'f2fs':
    packages.append('f2fs-tools')
if root_filesystem == 'btrfs':
    packages.append('btrfs-progs')


def post(step, echo, run, shell):
    """Post-installation steps (run in chroot)"""
    step('Post-installation step (shell in chroot)')
    run('bash', '-i')

    # enable ssh server (useful for servers)
    # step('SSH Daemon')
    # echo('PermitRootLogin yes') >> '/etc/ssh/sshd_config'
    # shell('systemctl enable sshd')
