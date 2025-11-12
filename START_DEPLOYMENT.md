# 🚀 Let's Deploy to Vercel + Railway - Step by Step

Follow these steps **in order**. Each step should take 2-5 minutes.

---

## ✅ Step 1: Deploy Backend to Railway (5 minutes)

### 1.1 - Open Railway Dashboard

Go to: https://railway.app

- Click "Login" or "Start a New Project"
- Sign in with your GitHub account
- No credit card required (you get $5 free credit)

### 1.2 - Create New Project

1. Click "+ New Project"
2. Select "Deploy from GitHub repo"
3. **If this is your first time:**
   - Click "Configure GitHub App"
   - Select your Entmoot repository
   - Click "Install & Authorize"
4. **Select your Entmoot repository**

### 1.3 - Add PostgreSQL Database

1. In your Railway project, click "+ New"
2. Select "Database"
3. Choose "Add PostgreSQL"
4. Railway will create a PostgreSQL database
5. ✅ Railway automatically sets the `DATABASE_URL` environment variable

### 1.4 - Add Redis

1. Click "+ New" again
2. Select "Database"
3. Choose "Add Redis"
4. Railway will create a Redis instance
5. ✅ Railway automatically sets the `REDIS_URL` environment variable

### 1.5 - Configure Backend Service

1. Click on your backend service (should be named after your repo)
2. Go to "Variables" tab
3. Click "+ New Variable" and add these one by one:

```
SECRET_KEY = [Click "Generate" or use: openssl rand -hex 32]
ENVIRONMENT = production
PORT = 8000
CORS_ORIGINS = *
```

**To generate SECRET_KEY in terminal:**
```bash
openssl rand -hex 32
```
Copy the output and paste it as the SECRET_KEY value.

### 1.6 - Generate Domain

1. Still in your backend service, go to "Settings" tab
2. Scroll to "Networking" section
3. Click "Generate Domain"
4. Copy the domain (e.g., `entmoot-backend.up.railway.app`)
5. **SAVE THIS URL** - you'll need it for Vercel!

### 1.7 - Deploy

Railway automatically deploys! Check the "Deployments" tab to see progress.

**Wait for deployment to finish** (usually 2-3 minutes)

### 1.8 - Test Backend

Open your Railway domain in browser:
```
https://your-backend.up.railway.app/health
```

You should see:
```json
{"status": "healthy"}
```

Also check the API docs:
```
https://your-backend.up.railway.app/docs
```

✅ **Backend is deployed!**

---

## ✅ Step 2: Deploy Frontend to Vercel (5 minutes)

### 2.1 - Update Frontend Config

First, let's set the backend URL in the frontend code:

**Option A - In Browser (Easier):**

We'll add the environment variable directly in Vercel dashboard (next step)

**Option B - In Code (More permanent):**

Open `/Users/aleksandrgaun/Downloads/Entmoot/frontend/.env.production`

Replace:
```
VITE_API_URL=https://your-backend.up.railway.app
```

With your actual Railway backend URL:
```
VITE_API_URL=https://entmoot-backend.up.railway.app
```

Then commit:
```bash
cd /Users/aleksandrgaun/Downloads/Entmoot
git add frontend/.env.production
git commit -m "Add production API URL"
git push
```

### 2.2 - Open Vercel Dashboard

Go to: https://vercel.com

- Click "Sign Up" or "Login"
- Sign in with your GitHub account

### 2.3 - Import Project

1. Click "Add New..." → "Project"
2. Find your Entmoot repository
3. Click "Import"

### 2.4 - Configure Build Settings

**Framework Preset:** Vite (should auto-detect)

**Root Directory:** Click "Edit" and enter: `frontend`

**Build Command:** `npm run build` (should be set)

**Output Directory:** `dist` (should be set)

**Install Command:** `npm install` (should be set)

### 2.5 - Add Environment Variable

Click "Environment Variables" section:

**Key:** `VITE_API_URL`
**Value:** `https://your-backend.up.railway.app` (your Railway URL)

Click "Add"

### 2.6 - Deploy!

Click "Deploy" button

Vercel will:
- Install dependencies
- Build your React app
- Deploy to global CDN

**Wait for deployment** (usually 1-2 minutes)

### 2.7 - Get Your Frontend URL

Once deployed, you'll see:

```
🎉 Your project is deployed!
https://entmoot.vercel.app
```

Copy this URL!

### 2.8 - Test Frontend

Open your Vercel URL in browser:
```
https://entmoot.vercel.app
```

You should see your Entmoot app!

---

## ✅ Step 3: Update CORS Settings (2 minutes)

Now that frontend is deployed, let's allow it to talk to the backend:

### 3.1 - Update Railway CORS

1. Go back to Railway dashboard
2. Click on your backend service
3. Go to "Variables" tab
4. Find `CORS_ORIGINS` variable
5. Update its value to:
   ```
   https://entmoot.vercel.app,https://*.vercel.app
   ```
   (This allows your Vercel domain and any preview deployments)

6. Railway will automatically redeploy (wait ~1 minute)

### 3.2 - Test Everything

Go to your Vercel URL and try:
1. Create a new project
2. Upload property boundary
3. Verify it works!

---

## 🎉 You're Done!

Your app is now deployed!

**Frontend:** https://entmoot.vercel.app
**Backend:** https://entmoot-backend.up.railway.app

---

## 📱 Share Your App

You can now share your Vercel URL with anyone!

---

## 🔄 Automatic Deployments

From now on, whenever you push to GitHub:

- **Railway** will automatically redeploy the backend
- **Vercel** will automatically redeploy the frontend

Just push your changes:
```bash
git add .
git commit -m "Your changes"
git push
```

---

## 🔧 Useful Commands

### View Backend Logs (Railway)

Go to Railway dashboard → Your service → "Logs" tab

### View Frontend Logs (Vercel)

Go to Vercel dashboard → Your project → "Deployments" → Click on deployment → "Logs"

### Redeploy

**Railway:**
- Dashboard → Service → "Deployments" → Click "..." → "Redeploy"

**Vercel:**
- Dashboard → Project → "Deployments" → Click "..." → "Redeploy"

---

## ❓ Troubleshooting

### Frontend can't connect to backend

**Check CORS:**
```bash
# Open browser console on your Vercel site
fetch('https://your-backend.up.railway.app/health')
  .then(r => r.json())
  .then(console.log)
```

**If you see CORS error:**
- Make sure Railway `CORS_ORIGINS` includes your Vercel URL
- Wait 1-2 minutes for Railway to redeploy

### Backend not responding

**Check Railway logs:**
- Railway dashboard → Service → Logs tab

**Common issues:**
- Missing environment variables
- Database not connected
- Check `DATABASE_URL` and `REDIS_URL` are set

### Build failures

**Vercel build fails:**
- Check Vercel deployment logs
- Make sure `frontend/.env.production` exists
- Verify `VITE_API_URL` is set in Vercel environment variables

**Railway build fails:**
- Check Railway deployment logs
- Verify Dockerfile is in root directory
- Check `railway.json` configuration

---

## 💰 Cost

**Free Tier:**
- Railway: $5 credit/month (enough for ~500 hours)
- Vercel: Unlimited frontend deployments

**If you go over:**
- Railway: ~$5-10/month
- Vercel: Still free for personal projects!

---

## 🎯 Next Steps

1. **Custom Domain:** Add your domain in Vercel settings
2. **Monitoring:** Set up error tracking (Sentry)
3. **Analytics:** Enable Vercel Analytics
4. **Backups:** Set up automated database backups

---

Need help? Check the detailed guide in `DEPLOY_VERCEL_HYBRID.md`
