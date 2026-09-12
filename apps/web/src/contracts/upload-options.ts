/* Generated from apps/contracts. Do not edit manually. */

export type MaxBytes = number;
export type MaxImages = number;
export type MaxPixels = number;
export type MediaTypes = string[];

export interface UploadOptions {
  max_bytes: MaxBytes;
  max_images: MaxImages;
  max_pixels: MaxPixels;
  media_types: MediaTypes;
  subjects: Subjects;
}
export interface Subjects {
  [k: string]: string;
}
