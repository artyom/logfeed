#!/usr/bin/env python

import os
import sys
import hashlib
import glob
import time
import gzip, bz2
import pickle
from collections import namedtuple

DEBUG = False
SLEEPTIME = 1
SAVE_PERIOD = 30
REREAD_PERIOD = 60

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
    return hashlib.sha1(s).hexdigest()

Logfile = namedtuple('Logfile', ['filename', 'fh'])

class LogFeed(object):
    """
    Usage:

        system_logs = LogFeed('/var/log/syslog*')
        for line in system_logs:
            process(line)

    The statefile used to store state (log position) between runs; follow mode
    would read new log messages indefinitely.
    """
    def __init__(self, pattern, statefile=None, follow=False, consumer=None):
        self.logfiles = []
        self.consumer = consumer
        self.pattern = pattern
        self.follow = follow
        self.update_logfiles()
        self.makesigmap()
        if statefile:
            self.statefile = statefile
        else:
            self.statefile = '/tmp/state.{0}'.format(hashlib.sha1(pattern).hexdigest())
        self.load_state()
        self.discard_processed()
        debug("files are: {0}".format('\n'.join(x.filename for x in self.logfiles)))
        debug("state is: {0} {1} {2}".format(self.saved_filename, self.saved_signature, self.saved_position))

    def update_logfiles(self):
        for i in self.logfiles: i.fh.close()
        logfiles = sorted(glob.glob(self.pattern), reverse=True)
        self.logfiles = map(lambda x: Logfile(x, open_any(x, 'r')), logfiles)

    def makesigmap(self):
        self.sigmap = dict(map(lambda x: (file_signature(x.fh), x.filename), self.logfiles))

    def save_state(self):
        debug("saving state")
        new_filename = "{0}.new".format(self.statefile)
        self.saved_position = self.current_file.tell()
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
            debug("discarding already processed files")
            # looking for last seen file position
            pos = 0
            for i in self.logfiles:
                if i.filename == last_seen_file:
                    pos = self.logfiles.index(i)
                    break
            # closing already processed files
            for i in self.logfiles[:pos]: i.fh.close()
            # trimming list
            self.logfiles = self.logfiles[pos:]

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
        while True:
            for logfile in self.logfiles:
                self.current_file = logfile.fh
                debug("processing file {0}".format(self.current_file.name))
                self.current_signature = file_signature(self.current_file)
                if self.current_signature == self.saved_signature:
                    self.current_file.seek(self.saved_position)
                # read the file until it ends
                for l in self.current_file:
                    if not self.consumer:
                        yield l
                    else:
                        self.consumer(l)
                self.save_state()

                # if we're on last file AND want to receive new updates
                if self.logfiles[-1] == logfile and self.follow:
                    cycles = 0
                    try:
                        while True:
                            cycles+=1
                            self.wait()
                            self.current_file.seek(self.current_file.tell())
                            for l in self.current_file:
                                if not self.consumer:
                                    yield l
                                else:
                                    self.consumer(l)
                            if not cycles % SAVE_PERIOD:
                                self.save_state()
                            if not cycles % REREAD_PERIOD:
                                self.save_state()
                                # try to detect if files were rotated
                                self.update_logfiles()
                                self.makesigmap()
                                self.discard_processed()
                                break
                    except KeyboardInterrupt:
                        # exit requested, saving state and breaking the loop
                        self.save_state()
                        self.follow = False
                        break
                else:
                    self.current_file.close()

            # one-shot run, do not re-read logfiles for possible rotation
            if not self.follow:
                break



if __name__ == "__main__":
    if not sys.argv[1:]:
        raise SystemExit("{0} /path/to/logfiles* (pattern)".format(sys.argv[0]))
    pattern = sys.argv[1]
    lf = LogFeed(pattern, follow=False)
    for line in lf:
        sys.stdout.write(line)
