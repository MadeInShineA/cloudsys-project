
Créez le cluster à partir du fichier de configuration :
```
kind create cluster --config kind-config.yaml --name iot-cluster
```

Vérifiez que les nœuds sont bien prêts :
```
kubectl get nodes
```
```
cd simulator
docker build -t oglelehub/simulator:1.0.1 .
docker push oglelehub/simulator:1.0.1
```

```
kubectl apply -f simulator-deployment.yaml
kubectl get pod
kubectl delete pod fifo-pod
```

Verifier
```
kubectl exec -it fifo-pod -c simulator -- cat /shared/my-fifo
```