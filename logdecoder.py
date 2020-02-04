import base64
filename="log.tar.txt"
file=open(filename)
encoded=file.read()
decoded=base64.b64decode(encoded.encode("utf-8"))
if True:
    fil=open("passwords.txt","wb")
    fil.write(decoded)
    fil.close()
file.close()
fi=open("log.tar.txt","w")
fi.write(encoded)
fi.close()

