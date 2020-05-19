import { async, ComponentFixture, TestBed } from '@angular/core/testing';
import {By} from '@angular/platform-browser';
import { FileUploadComponent } from './file-upload.component';
import { HttpClientTestingModule } from '@angular/common/http/testing';

describe('FileUploadComponent', () => {
  let component: FileUploadComponent;
  let fixture: ComponentFixture<FileUploadComponent>;

  const file1 = new File(['test1'], 'spec_test_file1.test', { type: 'text/plain' });
  const file2 = new File(['test2'], 'spec_test_file2.test', { type: 'text/plain' });


  beforeEach(async(() => {
    TestBed.configureTestingModule({
      imports: [
        HttpClientTestingModule
      ],
      declarations: [ FileUploadComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(FileUploadComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should add files to list', () => {
    let list = new DataTransfer();
    list.items.add(file1);
    list.items.add(file2);
    component.onSelectFile(list.files);

    expect(component.files.length).toEqual(2);
    expect(component.files[0]).toEqual({file: file1,
      status: "request send",
      progress: 0,
      icon: "schedule"});
    
  });
});
