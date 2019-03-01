import subprocess
import shlex
import os
import urllib.request
import urllib.parse


#
# Helpers to mimic shell
#


class CommandFailure(Exception):
    pass


class CommandOutput(str):
    """
    An object that represents the output of a command,
    that can be redirected to a file.
    """
    def __init__(self, str):
        self.str = str

    def __gt__(self, path):
        print('* >', path)
        with open(path, mode='w') as file:
            file.write(self.str)

    def __rshift__(self, path):
        print('* >>', path)
        with open(path, mode='a') as file:
            file.write(self.str)


def step(mesg):
    """
    Show that we are currently running a step
    The step names would match those described in the Installation Guide
    https://wiki.archlinux.org/index.php/Installation_guide
    """
    print(f'\033[1m:: {mesg}\033[0m')


def set_cmd_defaults(kwds: dict):
    """
    helper to set subprocess.run keyword arguments
    """
    kwds.setdefault('universal_newlines', True)
    kwds.setdefault('errors', 'replace')
    if 'input' not in kwds:
        kwds.setdefault('stdin', subprocess.DEVNULL)
    kwds.setdefault('stdout', subprocess.PIPE)
    kwds.setdefault('stderr', subprocess.PIPE)


def cmd_fail(command, result):
    """
    helper function to raise an CommandFailure exception
    """
    print(end=result.stdout)
    if result.stderr is not None:
        print(end=result.stderr)
    print('-' * 79)
    raise CommandFailure(
        f'The command failed with exit code {result.returncode}\n{command}')


def cmd_print(command: str):
    """
    prints the shlex.quoted command
    """
    print('>', command)


def run(*args, check=True, **kwds):
    """
    run the command given by args with subprocess.run

    returns a CommandOutput on success
    raises a CommandFailure on error
    """
    set_cmd_defaults(kwds)
    command = ' '.join(shlex.quote(arg) for arg in args)
    cmd_print(command)
    result = subprocess.run(
        args,
        **kwds,
    )
    if check and result.returncode != 0:
        cmd_fail(command, result)
    return CommandOutput(result.stdout)


def shell(command, *, check=True, **kwds):
    """
    run the command with subprocess.run(..., shell=True)

    returns a CommandOutput on success
    raises a CommandFailure on error
    """
    set_cmd_defaults(kwds)
    cmd_print(command)
    result = subprocess.run(command, shell=True, **kwds)
    if check and result.returncode != 0:
        cmd_fail(command, result)
    return CommandOutput(result.stdout)


def echo(what):
    """
    simulate the echo command by returning a CommandOutput object

    useful to write a file, like:
    >>> echo('foo') > '/path/to/bar.txt'
    """
    return CommandOutput(what + '\n')


#
# Setup code
#


def generate_mirrors(country='TW'):
    path = 'https://www.archlinux.org/mirrorlist'
    qs = urllib.parse.urlencode({
        'country': country,
        'protocol': ['http', 'https'],
        'ip_version': '4',
    })
    lines = []
    with urllib.request.urlopen(f'{path}?{qs}') as file:
        for line in file:
            if line.startswith(b'#'):
                line = line[1:]
            lines.append(line)
    return b''.join(lines)


def part(disk: str, partnum: int):
    if 'nvme' in disk:
        return f'{disk}p{partnum}'
    return f'{disk}{partnum}'


def usb_main():
    try:
        import config
    except ModuleNotFoundError:
        print('config module not found, downloading it...')
        run('curl', '-OL', 'https://github.com/afg984/larch/raw/master/config.py')
        print('make adjustments to config.py and re-run this script')
        raise SystemExit(1)

    assert config.disk != 'FIXME'

    if config.use_uefi:
        try:
            run('efibootmgr')
        except CommandFailure:
            raise SystemExit(
                'UEFI is disabled or unsupported\n'
                'Please enable it or set USE_UEFI to False')

    step('Partition the disks')
    if config.use_uefi:
        boot_typecode = 'ef00'
        boot_size = '1G'
    else:
        boot_typecode = 'ef02'
        boot_size = '1M'
    run('wipefs', '--all', config.disk)
    shell(
        f'sgdisk {config.disk} '
        '--zap-all --clear '
        f'--new=1:0:+{boot_size} --typecode=1:{boot_typecode} '
        '--largest-new=2 --typecode=2:8304')
    run('partprobe', config.disk)

    step('Format the partitions')
    if config.use_uefi:
        run('mkfs.fat', '-F32', part(config.disk, 1))
    if config.root_filesystem == 'btrfs':
        run('mkfs.btrfs', '-f', part(config.disk, 2))
    elif config.root_filesystem == 'ext4':
        run('mkfs.ext4', '-F', part(config.disk, 2))
    elif config.root_filesystem == 'xfs':
        run('mkfs.xfs', '-f', part(config.disk, 2))
    elif config.root_filesystem == 'f2fs':
        run('mkfs.f2fs', '-f', part(config.disk, 2))
    else:
        raise Exception(
            f'unsupported root_filesystem: {config.root_filesystem!r}')

    try:
        step('Mount the file systems')
        run('mount', part(config.disk, 2), '/mnt')
        if config.use_uefi:
            os.mkdir('/mnt/boot')
            run('mount', part(config.disk, 1), '/mnt/boot')

        step('Select the mirrors')
        echo(generate_mirrors()) > '/etc/pacman.d/mirrorlist'

        step('Install the base packages')
        run(
            'pacstrap',
            '/mnt',
            *config.packages,
            stdout=None,
        )

        step('Fstab')
        shell('genfstab -U /mnt') >> '/mnt/etc/fstab'

        step('Hostname')
        if config.hostname is not None:
            echo(config.hostname) > '/mnt/etc/hostname'

        step('Chroot')
        run('mount', '--bind', 'larch.py', '/mnt/root/larch.py')
        run('mount', '--bind', 'config.py', '/mnt/root/config.py')
        shell(
            f'arch-chroot /mnt python /root/install.py --chroot',
            stdout=None,
            stderr=None,
        )
    finally:
        step('Clean up')
        shell('umount -R /mnt', check=False)


def chroot_main():
    import config
    step('Time zone')
    shell('ln -sf /usr/share/zoneinfo/Asia/Taipei /etc/localtime')

    step('Locale')
    echo('LANG=en_US.UTF-8') > '/etc/locale.conf'
    echo('en_US.UTF-8 UTF-8') > '/etc/locale.gen'
    shell('locale-gen')

    step('Enable systemd services')
    run('systemctl', 'enable', *config.services)

    step('Initramfs')
    shell('mkinitcpio -p linux')

    step('Root password')
    if config.root_password is None:
        run('passwd')
    else:
        run('chpasswd', input=f'root:{config.root_password}')

    step('Boot loader')
    if config.use_uefi:
        shell(
            'grub-install '
            '--target=x86_64-efi --efi-directory=/boot --bootloader-id=arch')
    else:
        run(
            'grub-install',
            '--target=i386-pc',
            config.disk,
        )
    shell('grub-mkconfig -o /boot/grub/grub.cfg')


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--chroot', action='store_true')
    args = parser.parse_args()
    try:
        if args.chroot:
            chroot_main()
        else:
            usb_main()
    except CommandFailure as e:
        raise SystemExit(str(e))


if __name__ == '__main__':
    main()
