import hashlib
import sys

if len(sys.argv) > 2:
    ip = sys.argv[1]
    hashedpw = hashlib.md5(' '.join(sys.argv[2:])).hexdigest()
    with open("../opers.txt", "a") as f:
        f.write("%s|%s\n" % (ip, hashedpw))
    print("Oper entry added!")
else:
    print("Example: python add_oper.py 127.0.0.1 admin_password")
