import subprocess
import argparse
import time
import os
import signal
import errno
from sys import exit


def pid_exists(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.EPERM:
            return True
        return False
    return True


def send_signal(sig_type):
    pid = args["pid"]
    if pid and pid_exists(pid):
        os.kill(pid, signal.Signals[f"SIG{sig_type}"])


def on_post_error(executed_time, stderr):
    pid = args["pid"]
    sig_name = args["signal"]
    fail_script_path = args["fail"]
    interval = args["i"]

    with open("heat.log", "a+") as file:
        while True:
            line = stderr.readline()
            if not line:
                break
            file.write(f"{executed_time}: {line}")

    if pid:
        if pid_exists(pid):
            sig_type = sig_name if sig_name else "HUP"
            send_signal(sig_type)
        else:
            print('올바른 PID를 입력해주세요')
            exit(1)
    if fail_script_path:
        p = subprocess.Popen(fail_script_path,
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             shell=True,
                             universal_newlines=True)
        p.wait()
        os.environ["HEAT_FAIL_CODE"] = f"{p.returncode}"
        os.environ["HEAT_FAIL_TIME"] = f"{int(time.time())}"
        os.environ["HEAT_FAIL_INTERVAL"] = f"{interval}"
        os.environ["HEAT_FAIL_PID"] = f"{p.pid}"
        p.terminate()


def on_post_recovery():
    global fail_cnt
    cmd = command if command else args["s"]
    interval = args["i"]
    timeout = args["recovery_timeout"]
    threshold = args["threshold"]
    fault_signal = args["fault_signal"]
    success_signal = args["success_signal"]

    if fault_signal:
        send_signal(fault_signal)

    if timeout:
        started_time = int(time.time())
        while True:
            if int(time.time()) - started_time > timeout:
                break
            p = subprocess.Popen(cmd,
                                 stderr=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 shell=True,
                                 universal_newlines=True)
            p.wait()
            p.terminate()
            if p.returncode == 0:
                if success_signal:
                    send_signal(success_signal)
                return True
            fail_cnt += 1  # 검사를 지정된 간격으로 계속 수행하고, fail 횟수만 누적
            time.sleep(interval)
        return False
    else:
        recovery_cnt = threshold
        while recovery_cnt:
            recovery_cnt -= 1
            p = subprocess.Popen(cmd,
                                 stderr=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 shell=True,
                                 universal_newlines=True)
            p.wait()
            p.terminate()
            if p.returncode == 0:
                if success_signal:
                    send_signal(success_signal)
                return True
            fail_cnt += 1  # 검사를 지정된 간격으로 계속 수행하고, fail 횟수만 누적
        return False


def on_recovery(genesis_error_time, check_pid):
    recovery_script_path = args["recovery"]
    interval = args["i"]

    p = subprocess.Popen(recovery_script_path,
                         stderr=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         shell=True,
                         universal_newlines=True)
    p.wait()
    os.environ["HEAT_FAIL_CODE"] = f"{p.returncode}"
    os.environ["HEAT_FAIL_TIME"] = f"{genesis_error_time}"
    os.environ["HEAT_FAIL_TIME_LAST"] = f"{int(time.time())}"
    os.environ["HEAT_FAIL_INTERVAL"] = f"{interval}"
    os.environ["HEAT_FAIL_PID"] = f"{check_pid}"
    os.environ["HEAT_FAIL_CNT"] = f"{fail_cnt}"
    p.terminate()

    is_recovery_success = on_post_recovery()
    return is_recovery_success


def execute():
    global fail_cnt
    interval = args["i"]
    threshold = args["threshold"]
    cmd = command if command else args["s"]
    while True:
        res = subprocess.Popen(cmd,
                               stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               shell=True,
                               universal_newlines=True)
        executed_time = int(time.time())
        res.wait()
        res.terminate()
        if res.returncode:
            print(f"{executed_time}:", f"Failed: Exit Code {res.returncode}, details in heat.log")
            on_post_error(executed_time, res.stderr)
            fail_cnt += 1
        else:
            fail_cnt = 0
            print(f"{executed_time}: OK")

        if threshold and fail_cnt >= threshold:
            # fail 횟수를 기존에서 누적하고, 다시 recovery 를 호출한다.
            while True:
                if on_recovery(genesis_error_time=executed_time, check_pid=res.pid):  # 연속 누적 fail 횟수를 초기화하고 정상 모드로 진입
                    fail_cnt = 0
                    break
                fail_cnt += 1
        time.sleep(interval)


def check_valid_option():
    if args["s"]:
        if command:
            print(command, args["s"])
            print("Error: use either script or command")
            exit(1)
        elif not os.access(args["s"], os.X_OK):
            print(f"Failed: {args['s']} not executable")
            exit(1)
    if args["fail"] and not os.access(args["fail"], os.X_OK):
        print(f"Failed: {args['fail']} not executable")
        exit(1)
    if args["recovery"] and not os.access(args["recovery"], os.X_OK):
        print(f"Failed: {args['recovery']} not executable")
        exit(1)


def get_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-s")
    parser.add_argument("-i", type=int)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--signal")
    parser.add_argument("--fail")
    parser.add_argument("--recovery")
    parser.add_argument("--threshold", type=int)
    parser.add_argument("--recovery-timeout", type=int)
    parser.add_argument("--fault-signal")
    parser.add_argument("--success-signal")

    parsed = parser.parse_known_args()
    return vars(parsed[0]), " ".join(parsed[1])


if __name__ == '__main__':
    fail_cnt = 0
    args, command = get_args()
    check_valid_option()
    execute()
