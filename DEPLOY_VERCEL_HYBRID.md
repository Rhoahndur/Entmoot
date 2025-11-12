# Deploy Entmoot with Vercel (Hybrid Approach)

## 🎯 The Setup

- **Frontend**: Vercel (free, global CDN)
- **Backend + DB**: Railway (free $5 credit/month)

**Total Cost**: FREE (with credits) or $5-10/month
**Setup Time**: 10-15 minutes

---

## Part 1: Deploy Backend to Railway (5 minutes)

### Step 1: Sign Up for Railway

1. Go to https://railway.app
2. Sign up with GitHub
3. Get $5 free credit (no credit card needed)

### Step 2: Create New Project

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Navigate to project
cd /Users/aleksandrgaun/Downloads/Entmoot

# Create Railway project
railway init
```

### Step 3: Add Services

In Railway dashboard:

1. **Add PostgreSQL**
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway auto-creates `DATABASE_URL` variable

2. **Add Redis**
   - Click "New" → "Database" → "Add Redis"
   - Railway auto-creates `REDIS_URL` variable

3. **Deploy Backend**
   - Click "New" → "GitHub Repo"
   - Select your Entmoot repository
   - Set root directory: `/`
   - Railway will auto-detect Dockerfile

### Step 4: Configure Environment Variables

In Railway project settings, add these variables:

```bash
# Railway auto-sets these:
DATABASE_URL=postgresql://...  # Auto-set by Railway
REDIS_URL=redis://...          # Auto-set by Railway

# You need to add these:
SECRET_KEY=your-secret-key-here-generate-with-openssl-rand-hex-32
ENVIRONMENT=production
CORS_ORIGINS=https://your-app.vercel.app
PORT=8000
```

**Generate SECRET_KEY:**
```bash
openssl rand -hex 32
```

### Step 5: Deploy

Railway will auto-deploy from your GitHub repo.

**Get your backend URL:**
- In Railway dashboard, go to your backend service
- Click "Settings" → "Generate Domain"
- Copy the URL (e.g., `https://your-app.up.railway.app`)

**Test it:**
```bash
curl https://your-app.up.railway.app/health
```

---

## Part 2: Deploy Frontend to Vercel (5 minutes)

### Step 1: Update Frontend Config

Update the API URL in your frontend to point to Railway backend:

**Create `.env.production` in frontend directory:**

```bash
cd /Users/aleksandrgaun/Downloads/Entmoot/frontend

cat > .env.production << EOF
VITE_API_URL=https://your-app.up.railway.app
EOF
```

**Update API client** (if needed):

Check `frontend/src/api/client.ts` and make sure it uses the env variable:

```typescript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

### Step 2: Create `vercel.json`

Create configuration file for Vercel:

```bash
cat > /Users/aleksandrgaun/Downloads/Entmoot/frontend/vercel.json << 'EOF'
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
EOF
```

### Step 3: Deploy to Vercel

**Option A - Using Vercel Dashboard (Easiest)**

1. Go to https://vercel.com
2. Sign up with GitHub
3. Click "Add New Project"
4. Import your GitHub repository
5. Configure:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
6. Add Environment Variable:
   - `VITE_API_URL` = `https://your-app.up.railway.app`
7. Click "Deploy"

**Option B - Using Vercel CLI**

```bash
# Install Vercel CLI
npm install -g vercel

# Navigate to frontend
cd /Users/aleksandrgaun/Downloads/Entmoot/frontend

# Login
vercel login

# Deploy
vercel

# Follow prompts:
# - Link to existing project? No
# - Project name: entmoot
# - Directory: ./ (already in frontend/)
# - Build settings: Accept defaults

# Set environment variable
vercel env add VITE_API_URL
# Enter: https://your-app.up.railway.app

# Deploy to production
vercel --prod
```

### Step 4: Update CORS

Update Railway backend CORS settings:

In Railway dashboard → Backend service → Variables:

```bash
CORS_ORIGINS=https://your-app.vercel.app,https://your-app-*.vercel.app
```

Redeploy backend (Railway auto-redeploys on variable change).

---

## Part 3: Test Deployment

### Test Backend
```bash
curl https://your-app.up.railway.app/health
curl https://your-app.up.railway.app/docs
```

### Test Frontend
```bash
# Open in browser
open https://your-app.vercel.app

# Should load the app and connect to Railway backend
```

### Test Full Flow
1. Create a new project
2. Upload property boundary
3. Place some assets
4. Check that everything saves correctly

---

## 🔄 Automatic Deployments

Both services auto-deploy on git push:

```bash
git add .
git commit -m "Update app"
git push origin main

# Railway automatically deploys backend
# Vercel automatically deploys frontend
```

---

## 💰 Cost Breakdown

### Free Tier (No Credit Card)
- **Railway**: $5 credit/month (enough for small projects)
- **Vercel**: Free for personal projects
- **Total**: FREE

### Paid Tier
- **Railway**: $5-20/month (depends on usage)
- **Vercel**: Free for frontend
- **Total**: $5-20/month

### Resource Limits (Free Tier)
- Railway: $5 credit ≈ 500 hours uptime
- Vercel: Unlimited deployments, 100GB bandwidth

---

## 📊 Monitoring

### Railway
- View logs: Railway Dashboard → Service → Logs
- View metrics: Railway Dashboard → Service → Metrics
- Set up alerts: Railway Dashboard → Project Settings

### Vercel
- View deployments: Vercel Dashboard → Project
- View analytics: Vercel Dashboard → Analytics
- View logs: Vercel Dashboard → Deployment → Logs

---

## 🔧 Advanced Configuration

### Custom Domain

**For Frontend (Vercel):**
1. Vercel Dashboard → Project → Settings → Domains
2. Add your domain
3. Update DNS with provided values

**For Backend (Railway):**
1. Railway Dashboard → Service → Settings
2. Add custom domain
3. Update DNS with provided CNAME

### Environment-Specific Configs

**Staging + Production:**

Deploy to both environments:

**Railway:**
- Create separate projects for staging/production
- Or use Railway's environment feature

**Vercel:**
- Push to `main` branch → Production
- Push to `develop` branch → Preview deployment

---

## 🚨 Troubleshooting

### Frontend can't connect to backend

**Check CORS:**
```bash
# Test from browser console:
fetch('https://your-app.up.railway.app/health')
  .then(r => r.json())
  .then(console.log)
```

**Fix CORS in Railway:**
- Add your Vercel domain to `CORS_ORIGINS`
- Include wildcard for preview deployments: `https://*.vercel.app`

### Backend not responding

**Check Railway logs:**
- Railway Dashboard → Backend Service → Logs

**Common issues:**
- Database not connected (check `DATABASE_URL`)
- Environment variables missing
- Port configuration (should be 8000)

### Build failures

**Vercel build fails:**
- Check build logs in Vercel dashboard
- Verify `package.json` scripts are correct
- Make sure all dependencies are in `package.json`

**Railway build fails:**
- Check Dockerfile is valid
- Verify all required files are in repo
- Check Railway build logs

---

## 📈 Scaling

When you outgrow free tier:

### Railway Scaling
- Upgrade to Pro: $20/month base + usage
- Vertical scaling: Add more RAM/CPU
- Add read replicas for database

### Vercel Scaling
- Free tier is usually enough for frontend
- Upgrade to Pro if you need:
  - More bandwidth
  - Team features
  - Better analytics

---

## 🎯 Pros of This Setup

✅ **Vercel strengths:**
- Global CDN for fast frontend
- Automatic HTTPS
- Git-based deployments
- Zero configuration

✅ **Railway strengths:**
- Easy database setup
- Full Docker support
- No timeout limits
- Simple configuration

✅ **Combined benefits:**
- Separation of concerns
- Better performance
- Easier to scale
- Lower cost

---

## 📝 Summary

**Total Setup Time**: 10-15 minutes
**Total Cost**: FREE (or $5-10/month)

**You get:**
1. Frontend on Vercel's global CDN
2. Backend on Railway with PostgreSQL + Redis
3. Auto-deployments on git push
4. HTTPS on both
5. Easy monitoring and logs

**Commands to run:**

```bash
# 1. Deploy backend to Railway
railway login
railway init
# (add databases in dashboard, set env vars)

# 2. Deploy frontend to Vercel
cd frontend
vercel
vercel --prod

# Done! 🎉
```

---

## 🔗 Next Steps

1. Set up custom domain
2. Configure monitoring alerts
3. Set up automated backups
4. Add Sentry for error tracking
5. Set up staging environment

---

## 💡 Alternative: All-in-One Railway

If you prefer simpler setup, you can deploy BOTH frontend and backend to Railway:

```bash
# Just deploy everything to Railway
railway init
railway up

# Add databases
# Railway serves both frontend and backend
```

**But Vercel + Railway is better because:**
- Faster global frontend delivery
- Better separation of concerns
- Easier to scale each part independently
