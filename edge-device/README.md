
Toutes les commandes sont à lancer depuis le dossier `edge-device/`.

Créez le cluster à partir du fichier de configuration :
```
kind create cluster --config kind-config.yaml --name iot-cluster
```

Vérifiez que les nœuds sont bien prêts :
```
kubectl get nodes
```

Créez le secret contenant les certificats AWS IoT Core (fichiers dans `deployment/certs/`, ignorés par git) :
```
kubectl create secret generic iot-core-certs --from-file=deployment/certs/AmazonRootCA1.pem --from-file=deployment/certs/device.pem.crt --from-file=deployment/certs/private.pem.key
```

Déployez les simulateurs et le contrôleur :
```
kubectl apply -f deployment/statefulset-worker.yaml
kubectl apply -f deployment/pod-iot-controller.yaml
```

Ou lancer le script rebuild and deploy (depuis `deployment/`).

Héberger en local un broker mqtt (optionnel, à la place d'AWS IoT Core)
```
docker run -d \
  --name mosquitto-broker \
  -p 1883:1883 \
  -p 9001:9001 \
  eclipse-mosquitto
```

docker exec -it mosquitto-broker mosquitto_sub -h localhost -p 1883 -t "iot/devices/batch"
