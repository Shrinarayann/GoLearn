# GoLearn Docker Deployment

## Quick Start (Local Development)

### Prerequisites
- Docker and Docker Compose installed
- Google API Key
- Firebase credentials JSON file

### Build and Run Locally

1. **Copy environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your credentials.

2. **Ensure firebase-credentials.json is in the root directory**

3. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d --build
   ```

4. **Verify deployment:**
   ```bash
   curl http://localhost:8000/health
   ```

---

## Digital Ocean Deployment

### Option 1: App Platform (Recommended - Easiest)

1. **Push your code to GitHub**

2. **Create App on Digital Ocean:**
   - Go to Digital Ocean → Apps → Create App
   - Select your GitHub repository
   - Select "Dockerfile" as the build method

3. **Configure Environment Variables:**
   In the App settings, add these environment variables:
   ```
   GOOGLE_API_KEY=your_key
   FIREBASE_PROJECT_ID=your_project_id
   FIREBASE_STORAGE_BUCKET=your_bucket.appspot.com
   CORS_ORIGINS=https://your-frontend.vercel.app
   WORKERS=2
   ```

4. **Add Firebase Credentials:**
   - Option A: Base64 encode your credentials and add as env var
   - Option B: Use Digital Ocean's encrypted environment files

5. **Deploy!**

### Option 2: Droplet with Docker

1. **Create a Droplet:**
   - Choose Ubuntu 22.04 LTS
   - Select Docker from Marketplace (1-Click App)
   - Minimum: 2GB RAM / 1 vCPU ($12/month)
   - Recommended: 4GB RAM / 2 vCPU ($24/month)

2. **SSH into your Droplet:**
   ```bash
   ssh root@your_droplet_ip
   ```

3. **Clone your repository:**
   ```bash
   git clone https://github.com/your-username/GoLearn.git
   cd GoLearn
   ```

4. **Create environment file:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Fill in all required values including:
   - `GOOGLE_API_KEY`
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_STORAGE_BUCKET`
   - `CORS_ORIGINS` (your Vercel frontend URL)

5. **Upload Firebase credentials:**
   ```bash
   # From your local machine
   scp firebase-credentials.json root@your_droplet_ip:/root/GoLearn/
   ```

6. **Build and run:**
   ```bash
   docker-compose up -d --build
   ```

7. **Verify:**
   ```bash
   curl http://localhost:8000/health
   ```

### Setting up HTTPS with Nginx (Production)

1. **Install Nginx and Certbot:**
   ```bash
   apt update
   apt install nginx certbot python3-certbot-nginx
   ```

2. **Create Nginx config:**
   ```bash
   nano /etc/nginx/sites-available/golearn
   ```
   
   Add:
   ```nginx
   server {
       listen 80;
       server_name api.yourdomain.com;

       location / {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_cache_bypass $http_upgrade;
           
           # Timeout settings for long-running AI requests
           proxy_connect_timeout 300;
           proxy_send_timeout 300;
           proxy_read_timeout 300;
       }
   }
   ```

3. **Enable the site:**
   ```bash
   ln -s /etc/nginx/sites-available/golearn /etc/nginx/sites-enabled/
   nginx -t
   systemctl reload nginx
   ```

4. **Get SSL certificate:**
   ```bash
   certbot --nginx -d api.yourdomain.com
   ```

5. **Update CORS_ORIGINS in .env to use https**

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Google Gemini API key |
| `FIREBASE_PROJECT_ID` | Yes | Firebase project ID |
| `FIREBASE_STORAGE_BUCKET` | Yes | Firebase storage bucket |
| `CORS_ORIGINS` | Yes | Comma-separated frontend URLs |
| `DEBUG` | No | Enable debug mode (default: false) |
| `PORT` | No | Server port (default: 8000) |
| `WORKERS` | No | Uvicorn workers (default: 2) |

---

## Useful Commands

```bash
# View logs
docker-compose logs -f backend

# Restart service
docker-compose restart backend

# Rebuild after code changes
docker-compose up -d --build

# Stop everything
docker-compose down

# Clean up (removes volumes too)
docker-compose down -v
```

---

## Troubleshooting

**Container exits immediately:**
- Check logs: `docker-compose logs backend`
- Verify firebase-credentials.json exists
- Verify GOOGLE_API_KEY is set

**CORS errors from frontend:**
- Ensure `CORS_ORIGINS` includes your Vercel URL
- Include both http and https if needed

**Firebase authentication errors:**
- Ensure firebase-credentials.json is valid and mounted
- Check GOOGLE_APPLICATION_CREDENTIALS path

**Out of memory:**
- Increase Droplet size or reduce WORKERS count
- AI models require significant memory

**Slow responses:**
- AI processing takes time, increase proxy timeouts
- Consider larger Droplet for more workers
