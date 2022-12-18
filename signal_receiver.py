import signal
import os

catchable_sigs = set(signal.Signals) - {signal.SIGKILL, signal.SIGSTOP}
for sig in catchable_sigs:
    signal.signal(sig, lambda x, y: print("Signal Recieved:", signal.Signals(x).name))

print("running on", os.getpid())
input("Enter 'quit' to teminate> \n")
