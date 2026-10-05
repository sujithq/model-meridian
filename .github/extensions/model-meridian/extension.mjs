import { createCanvas, joinSession } from "@github/copilot-sdk/extension";

const MODEL_MERIDIAN_URL = "https://model-meridian.quintelier.dev/";

await joinSession({
  canvases: [
    createCanvas({
      id: "model-meridian",
      displayName: "Model Meridian",
      description: "Explore AI model intelligence and cost data.",
      open: async () => ({
        title: "Model Meridian",
        status: "Connected to model-meridian.quintelier.dev",
        url: MODEL_MERIDIAN_URL,
      }),
    }),
  ],
});
