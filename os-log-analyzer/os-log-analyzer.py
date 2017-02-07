import argparse
import re
from datetime import datetime

TIMESTAMP_LOG_RE = re.compile(r'(?P<timestamp>[0-9]{4}-[0-9]{2}-[0-9]{2} '
                              '[0-9]{2}:[0-9]{2}:[0-9]{2}.[0-9]{3}).*')


NOVA_VIF_WAITING_RE = re.compile(r'(?P<timestamp>[0-9]{4}-[0-9]{2}-[0-9]{2} '
                                 '[0-9]{2}:[0-9]{2}:[0-9]{2}.[0-9]{3}) .*'
                                 'Preparing to wait for external event '
                                 'network-vif-plugged-(?P<port_id>.*) from')

NOVA_VIF_PLUGGED_RE = re.compile(r'(?P<timestamp>[0-9]{4}-[0-9]{2}-[0-9]{2} '
                                 '[0-9]{2}:[0-9]{2}:[0-9]{2}.[0-9]{3}) .*'
                                 'Received event network-vif-plugged-'
                                 '(?P<port_id>.*) from')

L2_IFAZ_DETECTED_RE = re.compile(r'(?P<timestamp>[0-9]{4}-[0-9]{2}-[0-9]{2} '
                                 '[0-9]{2}:[0-9]{2}:[0-9]{2}.[0-9]{3}) .*'
                                 'Output received from .*"insert".*\["iface-id'
                                 '","(?P<port_id>.*)"],\["iface-status.*')

L2_WIRING_DONE_RE = re.compile(r'(?P<timestamp>[0-9]{4}-[0-9]{2}-[0-9]{2} '
                               '[0-9]{2}:[0-9]{2}:[0-9]{2}.[0-9]{3}) .*'
                               'Setting status for (?P<port_id>.*) to UP.*')

ANSI_ESCAPE_RE = re.compile(r'\x1b[^m]*m')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--nova_log', required=True, dest='nova_path',
                        help='n-cpu log')
    parser.add_argument('-a', '--agt_log', dest='agt_path',
                        help='q-agt.log')
    parser.add_argument('-s', '--server_log', dest='server_path',
                        help='q-svc.log')
    # parser.add_argument('-i', action='store' ,nargs='*', required=True)
    # parser.add_argument('--from', action='store', dest='from',

    args = parser.parse_args()

    ports = set()
    port_events = {}

    # Scan all vif-plugged events to grab the ids of the ports and nova times
    with open(args.nova_path, 'r') as nova_file:
        for line in nova_file:
            line = ANSI_ESCAPE_RE.sub('', line)
            m = NOVA_VIF_WAITING_RE.match(line)
            if m:
                port_id = m.group('port_id')
                port_events[port_id] = {}
                port_events[port_id]['nova_start'] = (
                    datetime.strptime(
                        m.group('timestamp'), '%Y-%m-%d %H:%M:%S.%f'))
                continue
            m = NOVA_VIF_PLUGGED_RE.match(line)
            if m:
                port_id = m.group('port_id')
                port_events[port_id]['nova_end'] = (
                    datetime.strptime(
                        m.group('timestamp'), '%Y-%m-%d %H:%M:%S.%f'))
                ports.add(port_id)

    if args.agt_path:
        # Scan events in ovs agent log to calculate time since ovsdb monitor
        # detects that the device is plugged and notifies server that it's UP
        with open(args.agt_path, 'r') as agt_file:
            for line in agt_file:
                line = ANSI_ESCAPE_RE.sub('', line)
                m = L2_IFAZ_DETECTED_RE.match(line)
                if m:
                    port_id = m.group('port_id')
                    port_events[port_id]['l2_start'] = (
                        datetime.strptime(
                            m.group('timestamp'), '%Y-%m-%d %H:%M:%S.%f'))
                    continue
                m = L2_WIRING_DONE_RE.match(line)
                if m:
                    port_id = m.group('port_id')
                    port_events[port_id]['l2_end'] = (
                        datetime.strptime(
                            m.group('timestamp'), '%Y-%m-%d %H:%M:%S.%f'))
    else:
        for port in ports:
            port_events[port]['l2_start'] = port_events[port]['l2_end'] = 0


    print("\nport-id\t\t\t\t\tnova time\tovs agent time\n")
    for port in ports:
        print('%s\t%s\t%s' %
            (port,
             port_events[port]['nova_end'] - port_events[port]['nova_start'],
             port_events[port]['l2_end'] - port_events[port]['l2_start']))

    print("\n")
    for k, v in port_events.iteritems():
        print(k, v)

if __name__ == '__main__':
    main()
