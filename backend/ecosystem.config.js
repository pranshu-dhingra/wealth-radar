module.exports = {
  apps: [
    {
      name: "wealth-radar-api",
      script: ".venv/bin/uvicorn",
      args: "app.main:app --host 0.0.0.0 --port 8000",
      cwd: "/home/ec2-user/wealth-radar/backend",
      interpreter: "none",
      env: {
        NODE_ENV: "production",
      },
      // Auto-restart on crash
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      // Logging
      out_file: "/home/ec2-user/logs/api-out.log",
      error_file: "/home/ec2-user/logs/api-error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
    },
  ],
};
