FROM arm64v8/node:8

WORKDIR /usr/src/app/

COPY package.json yarn.lock ./
RUN yarn install --pure-lockfile --no-progress

COPY Gruntfile.js tsconfig.json tslint.json ./
COPY public public
COPY scripts scripts
COPY emails emails

ENV NODE_ENV production
RUN ./node_modules/.bin/grunt build