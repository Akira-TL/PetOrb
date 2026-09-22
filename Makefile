.PHONY: build demo status stop android web server

build:
	./scripts/build-demo.sh

demo:
	./scripts/run-demo.sh

status:
	./scripts/status-demo.sh

stop:
	./scripts/stop-demo.sh

android:
	cd apps/android-camera-bridge && ./gradlew assembleDebug

web:
	cd apps/web && NEXT_PUBLIC_API_URL=$${NEXT_PUBLIC_API_URL:-http://127.0.0.1:8010} corepack pnpm build

server:
	cd apps/server && uv sync
