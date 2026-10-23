#!/bin/bash

# Arrêt du script en cas d'erreur
set -e

echo "=========================================="
echo "1. Suppression des anciens pods et ressources..."
echo "=========================================="
kubectl delete -f pod-iot-controller.yaml --ignore-not-found=true
kubectl delete -f statefulset-worker.yaml --ignore-not-found=true

echo ""
echo "=========================================="
echo "2. Reconstruction des images Docker..."
echo "=========================================="
# Si vous avez un Dockerfile séparé pour le contrôleur, ajustez le nom du fichier (-f Dockerfile.controller)
cd simulator/
docker build -t oglelehub/iot-worker:1.0.2 -f Dockerfile .
cd ../iot-controller/
docker build -t oglelehub/iot-controller:1.0.2 -f Dockerfile .
cd ..

echo ""
echo "=========================================="
echo "3. Chargement des images dans le cluster Kind..."
echo "=========================================="
# Remplacez "kind" par le nom de votre cluster si besoin (par défaut c'est "kind")
kind load docker-image oglelehub/iot-worker:1.0.2 --name iot-cluster
kind load docker-image oglelehub/iot-controller:1.0.2 --name iot-cluster

echo ""
echo "=========================================="
echo "4. Relance du pipeline dans Kubernetes..."
echo "=========================================="
kubectl apply -f pod-iot-controller.yaml
kubectl apply -f statefulset-worker.yaml

echo ""
echo "✨ Déploiement terminé avec succès ! Suivi des pods en cours..."
echo "------------------------------------------"
kubectl get pods -w