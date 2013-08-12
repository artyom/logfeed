#!/usr/bin/env python

import os
import sys
import sha
import glob
import time
import gzip, bz2
import pickle

DEBUG = False
SLEEPTIME = 1
SAVE_PERIOD = 30

def debug(message):
    if DEBUG:
        sys.stderr.write("DEBUG: {0}\n".format(message))

def open_any(filename, mode):
    """
    Opens regular files as well as .gz, .bz2 files
    """
    if filename.endswith('.gz'):
        return gzip.GzipFile(filename, mode)
    if filename.endswith('.bz2'):
        return bz2.BZ2File(filename, mode)
    return open(filename, mode)

def file_signature(f):
    """
    Returns file signature (hash of 1st line)
    """
    if isinstance(f, (file, gzip.GzipFile, bz2.BZ2File)):
        oldpos = f.tell()
        f.seek(0)
        s = f.readline()
        f.seek(oldpos)
    else:
        try:
            with open_any(f, 'r') as f:
                s = f.readline()
        except IOError:
            return None
    return sha.sha(s).hexdigest()

class LogFeed(object):
    """
    Usage:

        system_logs = LogFeed('/var/log/syslog*')
        for line in system_logs:
            process(line)
    """
    def __init__(self, pattern, statefile=None, follow=False):
        self.pattern = pattern
        self.follow = follow
        self.update_logfiles()
        self.makesigmap()
        if statefile:
            self.statefile = statefile
        else:
            self.statefile = '/tmp/state.{0}'.format(sha.sha(pattern).hexdigest())
        self.load_state()
        self.discard_processed()
        debug("files are: {0}".format('\n'.join(self.logfiles)))
        debug("state is: {0} {1} {2}".format(self.saved_filename, self.saved_signature, self.saved_position))

    def update_logfiles(self):
        self.logfiles = sorted(glob.glob(self.pattern), reverse=True)

    def makesigmap(self):
        self.sigmap = dict(map(lambda x: (file_signature(x), x), self.logfiles))

    def save_state(self):
        new_filename = "{0}.new".format(self.statefile)
        with open(new_filename, 'w') as f:
            pickle.dump(dict(
                position = self.current_file.tell(),
                signature = self.current_signature,
                filename = self.current_file.name
                ), f)
        os.rename(new_filename, self.statefile)

    def discard_processed(self):
        last_seen_file = self.sigmap.get(self.saved_signature)
        if last_seen_file:
            self.logfiles = self.logfiles[self.logfiles.index(last_seen_file):]

    def load_state(self):
        state = {}
        try:
            state = pickle.load(open(self.statefile, 'r'))
        except (IOError, EOFError):
            pass
        self.saved_position = state.get('position',0)
        self.saved_signature = state.get('signature')
        self.saved_filename = state.get('filename')

    def wait(self):
        time.sleep(SLEEPTIME)

    def __iter__(self):
        for filename in self.logfiles:
            with open_any(filename, 'r') as self.current_file:
                self.current_signature = file_signature(self.current_file)
                if self.current_signature == self.saved_signature:
                    self.current_file.seek(self.saved_position)
                # read the file until it ends
                for l in self.current_file:
                    yield l
                self.save_state()

                # if we're on last file AND want to receive new updates
                if self.logfiles[-1] == filename and self.follow:
                    cycles = 0
                    try:
                        while True:
                            cycles+=1
                            self.wait()
                            self.current_file.seek(self.current_file.tell())
                            for l in self.current_file:
                                yield l
                            if not cycles % SAVE_PERIOD:
                                self.save_state()
                    except KeyboardInterrupt:
                        self.save_state()



if __name__ == "__main__":
    if not sys.argv[1:]:
        raise SystemExit("{0} /path/to/logfiles* (pattern)".format(sys.argv[0]))
    pattern = sys.argv[1]
    lf = LogFeed(pattern, follow=False)
    for line in lf:
        sys.stdout.write(line)
