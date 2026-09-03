import type {MetadataRoute} from 'next';

const siteUrl='https://www.medicii.net';

export default function sitemap():MetadataRoute.Sitemap{
 return ['','/how-it-works','/security','/faq','/contact','/user-agreement'].map((path,index)=>({url:`${siteUrl}${path}`,lastModified:new Date(),changeFrequency:index===0?'weekly':'monthly',priority:index===0?1:0.7}));
}
