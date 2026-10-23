
Créez le cluster à partir du fichier de configuration :
```
kind create cluster --config kind-config.yaml --name iot-cluster
```

Lancer le script rebuild and deply

Vérifiez que les nœuds sont bien prêts :
```
kubectl get nodes
```

Héberger en local un broker mqtt
```
docker run -d \
  --name mosquitto-broker \
  -p 1883:1883 \
  -p 9001:9001 \
  eclipse-mosquitto
```

docker exec -it mosquitto-broker mosquitto_sub -h localhost -p 1883 -t "iot/devices/batch"