export function PredictionArc({ confidence }: { confidence: number }) {
  return <div className="prediction-arc">prediction confidence {(confidence * 100).toFixed(0)}%</div>;
}
