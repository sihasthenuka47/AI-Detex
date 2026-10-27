import {test,expect} from '@playwright/test';
test('private writing workflow, exports, profile, comparisons and deletion',async({page,request})=>{
 await request.delete('/api/data');
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'Workspace overview.'})).toBeVisible();
 await page.getByRole('button',{name:'New analysis',exact:true}).last().click();
 await page.getByLabel('Document title').fill('Browser test draft');
 await page.getByLabel('Your writing', {exact:true}).fill('The birds return in spring. The birds sing outside my window. I wrote these observations during a quiet morning.');
 await page.getByRole('button',{name:'Analyze writing'}).click();
 await expect(page.getByText('AI authorship probability unavailable — insufficient validated evidence',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Save analysis',exact:true}).click();
 await expect(page.getByText('Analysis saved to your private workspace.')).toBeVisible();
 await page.getByRole('button',{name:'Diversity',exact:true}).click();
 await expect(page.locator('.answer')).toContainText('distinct lowercase words');
 await page.getByRole('button',{name:'Reports',exact:true}).click();
 const download=page.waitForEvent('download');await page.getByRole('link',{name:'PDF',exact:true}).click();
 expect((await download).suggestedFilename()).toMatch(/\.pdf$/);
 await page.getByRole('button',{name:'Writing Style Profile',exact:true}).click();
 await page.getByLabel('Browser test draft').check();
 await page.getByLabel('I consent to using these documents as my private style reference.').check();
 await page.getByRole('button',{name:'Save reference',exact:true}).click();
 await expect(page.getByText('Writing reference saved.')).toBeVisible();
 await page.getByRole('button',{name:'Analysis History',exact:true}).click();
 await expect(page.locator('tbody tr')).toHaveCount(1);
 await page.reload();await page.getByRole('button',{name:'Analysis History',exact:true}).click();
 await expect(page.locator('tbody tr')).toHaveCount(1);
 for(const name of ['Originality Research','Settings','Help & methodology','Sentence Intelligence','Document Analyzer','Dashboard']){
  await page.getByRole('button',{name,exact:true}).click();await expect(page.locator('main h1')).toBeVisible();
 }
 await page.getByRole('button',{name:'Toggle color theme'}).click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 await page.screenshot({path:'../docs/dashboard-desktop.png',fullPage:true});
 expect(errors).toEqual([]);
 await request.delete('/api/data');
});
test('mobile navigation and editor have no horizontal overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');
 await page.getByRole('button',{name:'Toggle navigation'}).click();
 await page.getByRole('button',{name:'New Analysis',exact:true}).first().click();
 await expect(page.getByLabel('Your writing',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await page.screenshot({path:'../docs/editor-mobile.png',fullPage:true});
});
