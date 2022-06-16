#!/user/bin/env python3
# -*- coding: utf-8 -*-

import logging
import errno
import os
import select
import subprocess
import io
import time
from contextlib import contextmanager

OUT = "out"
ERR = "err"


def add_sudo(cmd):
    if os.geteuid() == 0:
        return cmd
    command = ['sudo', '-n']
    # command = ['sudo',]
    command.extend(cmd)
    return command


class PrivilegedPopen(subprocess.Popen):
    """
    Subclass of Popen that uses the kill command to send signals to the child
    process.

    The kill(), terminate(), and send_signal() methods will work as expected
    even if the child process is running as root.
    """

    def send_signal(self, sig):
        logging.info("Sending signal %d to child process %d", sig, self.pid)
        args = ['kill', "-%d" % sig, str(self.pid)]
        try:
            proc = make_proc(args, sudo=True)
            run(proc)
        except Exception as e:
            logging.warning("Error sending signal to child process %d: %s",
                            self.pid, e.err)


def make_proc(cmd, pipe=None, cwd=None, sudo=False):
    if sudo:
        cmd = add_sudo(cmd)
    cmd_class = PrivilegedPopen if sudo else subprocess.Popen
    proc = cmd_class(
        cmd,
        stdin=subprocess.PIPE if pipe else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd)
    return proc


def terminate(proc):
    try:
        if proc.poll() is None:
            logging.debug('Terminating process pid=%d' % proc.pid)
            proc.kill()
            proc.wait()
    except Exception as e:
        raise Exception("Failed to terminate process {}: {}".format(proc.pid, e))


@contextmanager
def terminating(proc):
    try:
        yield proc
    finally:
        terminate(proc)


def watch(proc):
    err = bytearray()
    for src, data in receive(proc):
        if src == OUT:
            yield data
        else:
            err += data


def uninterruptible(func, *args, **kwargs):
    """
    Call func with *args and *kwargs and return the result, retrying if func
    failed with EINTR. This may happen if func invoked a system call and the
    call was interrupted by signal.

    WARNING: Use only with functions which are safe to restart after EINTR.
    """
    while True:
        try:
            return func(*args, **kwargs)
        except EnvironmentError as e:
            if e.errno != errno.EINTR:
                raise


def receive(p, bufsize=io.DEFAULT_BUFFER_SIZE):
    """
    Receive data from a process, yielding data read from stdout and stderr
    until proccess terminates or timeout expires.

    Unlike Popen.communicate(), this supports a timeout, and allows
    reading both stdout and stderr with a single thread.

    Example usage::

        # Reading data from both stdout and stderr until process
        # terminates:

        for src, data in cmdutils.receive(p):
            if src == cmdutils.OUT:
                # handle output
            elif src == cmdutils.ERR:
                # handler errors

        # Receiving data with a timeout:

        try:
            received = list(cmdutils.receive(p, timeout=10))
        except cmdutils.TimeoutExpired:
            # handle timeout

    Arguments:
        p (`subprocess.Popen`): A subprocess created with
            subprocess.Popen or subprocess32.Popen or cpopen.CPopen.
        timeout (float): Number of seconds to wait for process. Timeout
            resolution is limited by the resolution of
            `common.time.monotonic_time`, typically 10 milliseconds.
        bufsize (int): Number of bytes to read from the process in each
            iteration.

    Returns:
        Generator of tuples (SRC, bytes). SRC may be either
        `cmdutils.OUT` or `cmdutils.ERR`, and bytes is a bytes object
        read from process stdout or stderr.

    """
    deadline = None
    remaining = None

    fds = {}
    if p.stdout:
        fds[p.stdout.fileno()] = OUT
    if p.stderr:
        fds[p.stderr.fileno()] = ERR

    if fds:
        poller = select.poll()
        for fd in fds:
            poller.register(fd, select.POLLIN)

        def discard(fd):
            if fd in fds:
                del fds[fd]
                poller.unregister(fd)

    while fds:
        print("Waiting for process (pid=%d, remaining=%s)",
              p.pid, remaining)
        # Unlike all other time apis, poll is using milliseconds
        remaining_msec = remaining * 1000 if deadline else None
        try:
            ready = poller.poll(remaining_msec)
        except select.error as e:
            if e.args[0] != errno.EINTR:
                raise
            print("Polling process (pid=%d) interrupted", p.pid)
        else:
            for fd, mode in ready:
                if mode & select.POLLIN:
                    data = uninterruptible(os.read, fd, bufsize)
                    if not data:
                        print("Fd %d closed, unregistering", fd)
                        discard(fd)
                        continue
                    yield fds[fd], data
                else:
                    print("Fd %d hangup/error, unregistering", fd)
                    discard(fd)
        if deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Exception("Timeout waiting for process pid={}".format(p.pid))

    if deadline is None:
        p.wait()
    else:
        # We need to wait until deadline, Popen.wait() does not support
        # timeout. Python 3 is using busy wait in this case with a timeout of
        # 0.0005 seocnds. In vdsm we cannot allow such busy loops, and we don't
        # have a need to support very exact wait time. This loop uses
        # exponential backoff to detect termination quickly if the process
        # terminates quickly, and avoid busy loop if the process is stuck for
        # long time. Timeout will double from 0.0078125 to 1.0, and then
        # continue at 1.0 seconds, until deadline is reached.
        timeout = 1.0 / 256
        while p.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Exception("Timeout waiting for process pid={}".format(p.pid))
            time.sleep(min(timeout, remaining))
            if timeout < 1.0:
                timeout *= 2
    print("Process (pid=%d) terminated", p.pid)


def run(p):
    with terminating(p):
        out, err = p.communicate(input)

    logging.debug(p.returncode, err)

    if p.returncode != 0:
        raise Exception("Command failed with rc={} out={} "
                        "err={}".format(p.returncode, out, err))

    return out


def exec_cmd(cmd, errorout=False, ret_code=0, cwd=None, sudo=False, pipe_fail=False):
    print(' '.join(cmd))
    p = make_proc(cmd=['/bin/bash',], pipe=True, cwd=cwd, sudo=sudo)
    if isinstance(cmd, list):
        cmd = ' '.join(cmd)
    if pipe_fail:
        cmd = 'set -o pipefail; %s' % cmd
    o, e = p.communicate(cmd)
    r = p.returncode
    if r != ret_code and errorout:
        raise Exception('failed to execute bash[%s], return code: %s, stdout: %s, stderr: %s' % (cmd, r, o, e))
    if r == ret_code:
        e = None
    return r, o, e

######################