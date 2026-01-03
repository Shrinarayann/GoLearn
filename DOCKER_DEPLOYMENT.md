# GoLearn Docker Deployment

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Google API Key
- Firebase credentials JSON file

### Build and Run

1. **Copy environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your `GOOGLE_API_KEY`

2. **Ensure firebase-credentials.json is in the root directory**

3. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **Or build and run with Docker directly:**
   ```bash
   # Build
   docker build -t golearn-backend .
   
   # Run
   docker run -d \
     -p 8000:8000 \
     -e GOOGLE_API_KEY=your_key_here \
     -v $(pwd)/firebase-credentials.json:/app/firebase-credentials.json \
     -v $(pwd)/logs:/app/logs \
     --name golearn-backend \
     golearn-backend
   ```

### Verify Deployment

Check if the service is running:
```bash
curl http://localhost:8000/health
```

View logs:
```bash
docker logs golearn-backend -f
```

### Stop and Remove

```bash
# With Docker Compose
docker-compose down

# With Docker
docker stop golearn-backend
docker rm golearn-backend
```

## Production Deployment

For production, consider:
1. Use environment-specific `.env` files
2. Set up reverse proxy (Nginx) with SSL
3. Configure proper logging and monitoring
4. Use Docker secrets for sensitive data
5. Set up automated backups for Firebase data

## Troubleshooting

**Container exits immediately:**
- Check logs: `docker logs golearn-backend`
- Verify firebase-credentials.json exists
- Verify GOOGLE_API_KEY is set

**Port already in use:**
- Change port mapping: `-p 8080:8000` instead of `-p 8000:8000`

**Firebase authentication errors:**
- Ensure firebase-credentials.json is valid
- Check file permissions
