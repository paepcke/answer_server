#!/usr/bin/env python
'''
Created on Nov 18, 2013

@author: paepcke

Starts the answer_server.py script in the background, and 
then exits. Initially collects all (the optional) args from
the user. These are the args passed to the __init__() method
of AnswerServer (in answer_server.py). They are all related
to enabling the AnswerServer instance to access a MySQL DB
to get answers. MySQL: host, port, uid, pwd, and db.

'''
import argparse
import getpass
import os
import subprocess
import sys
import tempfile


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='answer_server')
    parser.add_argument('-u', '--mysql-user',
                        help='Have answer server log into the MySQL server under given user name',
                        dest='mysqlUsername',
                        default=getpass.getuser()
                        )
    parser.add_argument('-p', '--mysql-password', 
                        help='Ask for password to the MySQL server.', 
                        dest='askPwd',
                        action='store_true');

    parser.add_argument('-m', '--mysql-host', 
                        help='Where the MySQL server is located: a host name. Default: localhost', 
                        dest='mysqlHost',
                        default='localhost');
                        
    parser.add_argument('-t', '--mysql-port', 
                        help='Port where the MySQL server is listening. Default: 3306', 
                        dest='mysqlPort',
                        default=3306);
                        
#     parser.add_argument('-', '--mysql-db', 
#                         help='MySQL database to connect to. Default: test', 
#                         dest='mysqlDB',
#                         default='test');

    
    args = parser.parse_args()

    if args.askPwd:
        mysqlPWD = getpass.getpass("Password for %s on MySQL server at %s: " % (args.mysqlUsername, args.mysqlHost))
    else:
        mysqlPWD = "''"

    answerServerPath = os.path.join(os.path.dirname(__file__), 'answer_server.py')
    mysqldbDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../json_to_relation/json_to_relation')
    # Write the MySQL pwd to a tmp file, where it will be picked up 
    # by answer_server, who removes the file. This is done so the
    # pwd doesn't show up in ps -ef:
    pwdTmpFile = tempfile.NamedTemporaryFile(delete=False)
    pwdTmpFile.write(mysqlPWD)
    
    pythonPathCmd = 'export PYTHONPATH=%s:$PYTHONPATH; ' % mysqldbDir
    nohupCommand = 'nohup %s %s %s %s %s' %\
                    (answerServerPath,
                     args.mysqlHost,
                     args.mysqlPort, 
                     args.mysqlUsername,
                     pwdTmpFile.name
                     )

    subprocess.Popen(pythonPathCmd + nohupCommand, shell=True)
    sys.exit()