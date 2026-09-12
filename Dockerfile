# Production Dockerfile for ERPNext on Azure Container Apps
FROM frappe/erpnext:v15

# Set workspace environment
USER frappe
WORKDIR /home/frappe/frappe-bench

# Copy current repository changes into apps/erpnext
COPY --chown=frappe:frappe . /home/frappe/frappe-bench/apps/erpnext

# Expose Web Server & Socket.io ports
EXPOSE 8000 9000

CMD ["bench", "start"]
