// 사진 올리기 전에 브라우저에서 줄인다(기획서 5.6): 긴 변 1080px 이하, 500KB(512,000바이트) 이하.
export const MAX_BYTES = 500 * 1024
const MAX_SIDE = 1080

const toBlob = (c: HTMLCanvasElement, quality: number) =>
  new Promise<Blob | null>((resolve) => c.toBlob(resolve, 'image/jpeg', quality))

/** 이미지 파일을 읽어 JPEG로 줄인다. 그림이 아니거나 용량을 못 맞추면 Error. */
export async function shrinkImage(file: File): Promise<Blob> {
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  } catch {
    throw new Error('사진을 읽을 수 없어요. jpg, png, webp 파일을 골라 주세요')
  }
  let scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height))
  // 품질을 낮추고, 그래도 크면 크기를 줄여 다시 시도한다
  for (let attempt = 0; attempt < 5; attempt++) {
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(bitmap.width * scale))
    canvas.height = Math.max(1, Math.round(bitmap.height * scale))
    const ctx = canvas.getContext('2d')
    if (!ctx) break
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    for (const q of [0.85, 0.7, 0.55, 0.4]) {
      const blob = await toBlob(canvas, q)
      if (blob && blob.size <= MAX_BYTES) {
        bitmap.close()
        return blob
      }
    }
    scale *= 0.75
  }
  bitmap.close()
  throw new Error('사진 용량을 줄이지 못했어요. 다른 사진을 골라 주세요')
}
