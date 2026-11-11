'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {chooseDock}=require('../src/panel.js');
test('wide fixture docks in right gutter without intersecting main content',()=>{const result=chooseDock(1365,{left:357.5,right:1007.5,width:650},330);assert.equal(result.collapsed,false);assert.ok(result.left>=1007.5+12);assert.ok(result.left+330<=1365-12);});
test('uses left gutter if right has insufficient room',()=>{const result=chooseDock(1365,{left:400,right:1300,width:900},330);assert.equal(result.collapsed,false);assert.ok(result.left+330<=400-12);});
test('narrow viewport defaults to compact badge rather than covering main controls',()=>{assert.equal(chooseDock(800,{left:75,right:725,width:650},330).collapsed,true);assert.equal(chooseDock(375,{left:0,right:375,width:375},310).collapsed,true);});
test('unknown or invalid geometry defaults to collapsed without reading content',()=>{assert.equal(chooseDock(1365,null,330).collapsed,true);assert.equal(chooseDock(1365,{left:0,right:0,width:0},330).collapsed,true);});
