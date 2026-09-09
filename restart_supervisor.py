import argparse, json, os, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
STATUS=ROOT/"restart_status.json"
LOG=ROOT/"logs"/"restart_bootstrap.log"
LOG.parent.mkdir(parents=True,exist_ok=True)

def log(msg):
    line=f"{datetime.now().isoformat(timespec='milliseconds')}  {msg}\n"
    try:
        with LOG.open("a",encoding="utf-8") as f:f.write(line)
    except Exception: pass

def status(request_id, stage, message, success=False, old_pid=0):
    payload={
        "request_id":request_id,"stage":stage,"message":message,"success":bool(success),
        "bootstrap_pid":os.getpid(),"old_jarvis_pid":old_pid,
        "updated_at":datetime.now().isoformat(timespec="milliseconds"),
    }
    try:
        tmp=STATUS.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload,indent=2),encoding="utf-8")
        os.replace(tmp,STATUS)
    except Exception as exc:
        log(f"status write failed: {exc}")
    log(f"{stage}: {message}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--old-pid",type=int,default=0)
    ap.add_argument("--request-id",required=True)
    args=ap.parse_args()

    # Handshake immediately, before PowerShell or any shutdown action.
    status(args.request_id,"supervisor-ready","Python restart bootstrap is alive.",old_pid=args.old_pid)

    ps1=ROOT/"HARD_RESTART_ALL_SYSTEMS.ps1"
    if not ps1.exists():
        status(args.request_id,"failure",f"Restart PowerShell script missing: {ps1}",old_pid=args.old_pid)
        return 31

    # Give jarvis.py time to observe the handshake and finish its response.
    time.sleep(2.0)

    cmd=[
        "powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass",
        "-File",str(ps1),"-OldJarvisPid",str(args.old_pid),"-RequestId",args.request_id,
    ]
    log("Launching PowerShell restart worker.")
    try:
        proc=subprocess.Popen(cmd,cwd=str(ROOT))
        rc=proc.wait()
    except Exception as exc:
        status(args.request_id,"failure",f"Could not launch PowerShell restart worker: {exc}",old_pid=args.old_pid)
        return 32

    log(f"PowerShell restart worker exited rc={rc}")
    # PowerShell owns final status. Only write failure if it died without doing so.
    if rc!=0:
        try:
            current=json.loads(STATUS.read_text(encoding="utf-8-sig"))
        except Exception:
            current={}
        if current.get("request_id")!=args.request_id or current.get("stage") not in {"failure","complete"}:
            status(args.request_id,"failure",f"Restart worker exited with code {rc}.",old_pid=args.old_pid)
    return rc

if __name__=="__main__":
    raise SystemExit(main())
