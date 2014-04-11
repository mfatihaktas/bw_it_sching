#include <stdio.h>
#include <iostream>
#include <string.h>
using namespace std;

class FvConfig
{
private:
public:
	string exec(char* cmd);
	void getFVStarted();
	void doFVCleaning();
};

string FvConfig::exec(char* cmd) {
    FILE* pipe = popen(cmd, "r");
    if (!pipe) return "ERROR";
    char buffer[128];
    std::string result = "";
    while(!feof(pipe)) {
    	if(fgets(buffer, 128, pipe) != NULL)
    		result += buffer;
    }
    pclose(pipe);
    return result;
}

//This methods are not complete is gonna be used just for INITIAL purposes
//Reason: To make things more autonomous
void FvConfig::getFVStarted(){
	string str;
	
	str = exec((char*)"./fvcommands.sh as");
	cout<<str<<endl;
	cout<<"___________________________________"<<endl;
	
	str = exec((char*)"./fvcommands.sh af");
	cout<<str<<endl;
	cout<<"___________________________________"<<endl;
}

void FvConfig::doFVCleaning(){
	string str;
	
	str = exec((char*)"./fvcommands.sh rs");
	cout<<str<<endl;
	cout<<"___________________________________"<<endl;
	/*
	str = exec("./fvcommands.sh rf 1");
	cout<<str<<endl;
	cout<<"___________________________________"<<endl;
	
	str = exec("./fvcommands.sh rf 2");
	cout<<str<<endl;
	cout<<"___________________________________"<<endl;
	*/
}

int main () {
	FvConfig fvc;
	
	fvc.getFVStarted();
	string s="";
	getline(cin, s);
	//Clear FV
	fvc.doFVCleaning();
	return 0;
}
