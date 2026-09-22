##### This shell script converts all the mp3 files inside the subdirectories. #####
##### This requires the package "sox" to be pre-installed. #####
##### If you cannot run this file, give the execution permission using the command "chmod +x mp3_to_wav.sh" #####
##### After successful conversion, you may delete the mp3 files using the command "rm */*.mp3" #####
#!/bin/bash
OIFS="$IFS"
IFS=$'\n'
for i in $(find . -type f -name "*.mp3") 
do
	j=$i
	sox "$i" "${j/.mp3/.wav}" 
done
IFS="$OIFS"