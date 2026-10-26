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
echo "2. Relance du pipeline dans Kubernetes..."
echo "=========================================="
kubectl apply -f pod-iot-controller.yaml
kubectl apply -f statefulset-worker.yaml

echo ""
echo "✨ Déploiement terminé avec succès ! Suivi des pods en cours..."
echo "------------------------------------------"
kubectl get pods -w
