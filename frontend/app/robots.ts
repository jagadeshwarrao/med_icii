import type {MetadataRoute} from 'next';

export default function robots():MetadataRoute.Robots{
 return {rules:{userAgent:'*',allow:'/',disallow:['/admin/','/dashboard','/checkout','/orders','/profile','/quotes','/login','/register','/forgot-password','/reset-password']},sitemap:'https://www.medicii.net/sitemap.xml'};
}
