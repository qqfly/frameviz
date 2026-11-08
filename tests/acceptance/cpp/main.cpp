#include <frameviz/viz.hpp>
#include <frameviz/client.hpp>
#include <iostream>
#include <future>
#include <cmath>
int main(int argc, char** argv) {
  if (argc != 3) return 2;
  auto viz = frameviz::Viz::connect(argv[1], argv[2]);
  auto other = frameviz::Viz::connect(argv[1], argv[2]);
  auto handle = viz->addBox({0.4f,0.4f,0.4f}, {1.f,2.f,3.f}, {0,0,0,1}, {0.2f,0.6f,0.9f});
  const auto pose = viz->getCameraPose();
  const size_t counts[] = {4096,25000,100000,150000};
  std::vector<std::future<frameviz::json>> tasks;
  for (int i=0;i<4;++i) tasks.push_back(std::async(std::launch::async,[&,i] {
    auto& target=*(i%2 ? other : viz);
    std::vector<float> points(counts[i]*3);
    for (size_t j=0;j<points.size();++j) points[j]=float(j%997)/997.f;
    auto cloud=target.addPoints(points,frameviz::Color{.2f,.4f,.8f},1.f);
    for (int n=0;n<5;++n) {
      auto current=target.getCameraPose();
      for(int k=0;k<3;++k) if(std::abs(current.eye[k]-pose.eye[k])>1e-4) throw std::runtime_error("Mismatched concurrent camera query");
    }
    return frameviz::json{{"handle",cloud},{"count",counts[i]}};
  }));
  frameviz::json clouds=frameviz::json::array();
  for(auto& task:tasks) clouds.push_back(task.get());
  std::cout << frameviz::json({{"handle",handle},{"view_id",viz->viewId()},{"scene_id",viz->sceneId()}, {"eye",{pose.eye[0],pose.eye[1],pose.eye[2]}},{"clouds",clouds},{"concurrent_queries",20}}).dump() << std::endl;
}
