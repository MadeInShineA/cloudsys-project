
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

Créez la ConfigMap contenant la configuration du simulateur (`deployment/simulator/config.yaml`, pas besoin de rebuild l'image après une modification) :
```
kubectl create configmap simulator-config --from-file=config.yaml=deployment/simulator/config.yaml
```

Déployez les simulateurs, l'analyseur edge et le contrôleur :
```
kubectl apply -f deployment/statefulset-worker.yaml
kubectl apply -f deployment/deployment-edge-analyser.yaml
kubectl apply -f deployment/pod-iot-controller.yaml
```

L'analyseur (`deployment/edge-analyser/`) lit la télémétrie dans SQLite, détecte surchauffe, erreurs, statut `degraded` et machines muettes, et écrit des alertes que le contrôleur envoie immédiatement sur `group-8/iot/devices/alert`. Il est optionnel : sans lui (ou s'il ne répond plus depuis `ANALYZER_TIMEOUT` s), le contrôleur envoie la télémétrie normalement.

Ou lancer le script rebuild and deploy (depuis `deployment/`).

Après une modification de la config du simulateur, supprimez le cluster (`kind delete cluster --name iot-cluster`) puis recréez-le avec les étapes ci-dessus.

Héberger en local un broker mqtt (optionnel, à la place d'AWS IoT Core)
```
docker run -d \
  --name mosquitto-broker \
  -p 1883:1883 \
  -p 9001:9001 \
  eclipse-mosquitto
```

docker exec -it mosquitto-broker mosquitto_sub -h localhost -p 1883 -t "iot/devices/batch"
