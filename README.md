# LogFeed: read log messages from rotated files

`LogFeed` can read messages from rotated log. Consider the usual setup for
`messages` logfile in standard linux system:

	/var/log/messages.4.gz
	/var/log/messages.3.gz
	/var/log/messages.2.gz
	/var/log/messages.1
	/var/log/messages

`LogFeed` can abstract this separation, so you can iterate over log messages
from oldest to newest.

## Features

* uncompressed, gzipped (`.gz`) or bzipped (`.bz2`) files support;
* stores log position, so on successive run only new messages would be read;
* correctly handles log rotation (even while reading file);
* locks on state file;
* can be used in *follow mode* to continuously yield new messages as they're
  become available.

## Usage

	from logfeed import LogFeed

	system_logs = LogFeed('/var/log/syslog*')
	for line in system_logs:
	    process(line)

If you need to be sure that log position is advanced only if line was
successfully processed, you can use the following syntax:

	from logfeed import LogFeed

	system_logs = LogFeed('/var/log/syslog*', consumer=process)
	for line in system_logs:
	    pass

If `process` function raises an exception, log position won't be advanced
(though you can have some duplicate lines on successive run).
