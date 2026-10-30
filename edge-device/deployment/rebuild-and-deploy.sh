#!/bin/bash

# Arrêt du script en cas d'erreur
set -e

echo "=========================================="
echo "1. Suppression des anciens pods et ressources..."
echo "=========================================="
kubectl delete -f pod-iot-controller.yaml --ignore-not-found=true
kubectl delete -f deployment-edge-analyser.yaml --ignore-not-found=true
kubectl delete -f statefulset-worker.yaml --ignore-not-found=true

echo ""
echo "=========================================="
echo "2. Relance du pipeline dans Kubernetes..."
echo "=========================================="
kubectl create secret generic iot-core-certs --from-file=certs/AmazonRootCA1.pem --from-file=certs/device.pem.crt --from-file=certs/private.pem.key
kubectl create configmap simulator-config --from-file=config.yaml=simulator/config.yaml
kubectl apply -f pod-iot-controller.yaml
kubectl apply -f deployment-edge-analyser.yaml
kubectl apply -f statefulset-worker.yaml

echo ""
echo "✨ Déploiement terminé avec succès ! Suivi des pods en cours..."
echo "------------------------------------------"
kubectl get pods -w
