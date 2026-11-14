"""Reusable updater-bootstrap CLI for NON-Python host applications.

The actual implementation is in frb_update.bootstrap, the very same package
called by FRB Launch. This optional EXE is only an invocation adapter.
"""
import argparse
import json
import os
from pathlib import Path
from frb_update.bootstrap import check_feeds,ensure_updater,prepare_request,start_updater

def main(argv=None):
    parser=argparse.ArgumentParser(description='Common Updater bootstrapping CLI')
    parser.add_argument('--updater-feed',required=True)
    parser.add_argument('--product-feed',required=True)
    parser.add_argument('--install-root',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--host-pid',type=int,required=True)
    parser.add_argument('--host-exe',required=True)
    parser.add_argument('--allow-local-for-test',action='store_true')
    args=parser.parse_args(argv)
    try:
        updater,product=check_feeds(args.updater_feed,args.product_feed,
                                     allow_local=args.allow_local_for_test)
        binary=ensure_updater(args.install_root,updater,allow_local=args.allow_local_for_test)
        request=prepare_request(product,args.work_dir,allow_local=args.allow_local_for_test)
        process=start_updater(binary,request=request,install_root=args.install_root,
                              host_pid=args.host_pid,host_binary=args.host_exe,
                              allow_local=args.allow_local_for_test)
        print(json.dumps({'started':True,'updater_pid':process.pid,'updater_version':updater['version'],
                          'product_version':product['version']},ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({'started':False,'error':str(exc)},ensure_ascii=False))
        return 1
if __name__=='__main__':raise SystemExit(main())
