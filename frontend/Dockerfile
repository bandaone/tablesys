FROM node:22-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Expose port (matches vite.config.ts server.port)
EXPOSE 3002

# Run the development server
CMD ["npm", "run", "dev"]
