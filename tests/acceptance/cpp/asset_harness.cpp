#include "urdf_robot/asset_server.hpp"
#include <chrono>
#include <thread>
int main(int argc,char** argv) { if(argc!=3)return 2;urdf_robot::AssetServer server(argv[1],std::stoi(argv[2]));if(!server.start())return 3;std::this_thread::sleep_for(std::chrono::seconds(60));server.stop();}
