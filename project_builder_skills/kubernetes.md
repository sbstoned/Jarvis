# Kubernetes / Helm
Treat deployment manifests as a distinct component. Keep image, ports, probes, resources, config/secrets references and service selectors consistent. Prefer `helm lint`/template validation and client-side Kubernetes validation before deployment. Do not require a live cluster merely to prove source compilation unless the user explicitly requests deployment verification.
