import re

msgg = "Hello**World*This is a**Test**String"
msg_split = re.split(r'[\s\n:*]+|\*\*', msgg)
print(msg_split)
