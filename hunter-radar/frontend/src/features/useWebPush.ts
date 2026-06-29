/**
 * FE-142: useWebPush — Web Push 订阅集成(VAPID + Service Worker)
 *
 * 流程:
 * 1. 获取 VAPID 公钥
 * 2. 注册 Service Worker
 * 3. 调用 pushManager.subscribe()
 * 4. POST subscription 到后端
 *
 * 首次进入预警页时自动触发。
 */
import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";

export type PushStatus = "unsupported" | "unsubscribed" | "subscribing" | "subscribed" | "error";

export interface UseWebPushReturn {
  status: PushStatus;
  subscribe: () => Promise<void>;
  errorMessage: string | null;
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function useWebPush(): UseWebPushReturn {
  const { t } = useTranslation();
  const [status, setStatus] = useState<PushStatus>(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator) || !("PushManager" in window)) {
      return "unsupported";
    }
    return "unsubscribed";
  });
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const subscribe = useCallback(async () => {
    if (status === "unsupported" || status === "subscribing") return;

    setStatus("subscribing");
    setErrorMessage(null);

    try {
      // 1. Get VAPID public key
      const { public_key } = await api.getVapidPublicKey();

      // 2. Register SW
      const registration = await navigator.serviceWorker.ready;

      // 3. Check existing subscription
      let subscription = await registration.pushManager.getSubscription();

      if (!subscription) {
        // 4. Subscribe
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(public_key) as BufferSource,
        });
      }

      // 5. Send subscription to backend
      const json = subscription.toJSON();
      await api.createPushSubscription({
        endpoint: json.endpoint ?? "",
        p256dh: json.keys?.p256dh ?? "",
        auth: json.keys?.auth ?? "",
      });

      setStatus("subscribed");
    } catch (err) {
      console.error("Web Push subscribe failed:", err);
      setErrorMessage(
        err instanceof Error ? err.message : t("alerts.push.unknownError"),
      );
      setStatus("error");
    }
  }, [status, t]);

  return { status, subscribe, errorMessage };
}
