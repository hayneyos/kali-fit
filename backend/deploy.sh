git pull
sudo docker images -f "dangling=true" -q | xargs sudo docker rmi -f
       sudo docker ps -a -q --filter "status=exited" | xargs docker rm
       sudo docker-compose down --rmi all --volumes --remove-orphans
       sudo docker-compose up -d --build

